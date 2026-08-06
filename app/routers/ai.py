# app/routers/ai.py
"""
AI Management Router - Connects frontend AI Manager to the AutoPilot knowledge base.

Strategy:
  1. Try Supervity cloud workflow (fast path, 15s timeout) if SUPERVITY_API_KEY + SUPERVITY_WORKFLOW_ID are set.
  2. On timeout/error OR if keys not configured → fall back to local database-driven response engine.
"""

import json
import logging
import os
import re
from datetime import datetime, timezone
import httpx
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..core.database import get_db
from ..models.hackathon import (
    Issue, KnowledgeBase, UserDirectory, CSATSurvey
)
from ..models.workbench import WorkbenchItem
from ..schemas.ai import AIChatRequest, AIChatResponse
from ..security import get_current_user

log = logging.getLogger(__name__)

router = APIRouter(prefix="/ai", tags=["AI Manager"])


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _env(key: str, default: str = "") -> str:
    val = os.getenv(key, default)
    return val.strip().strip('"').strip("'") if val else default


def parse_supervity_output(raw_text: str) -> str:
    """Parse SSE stream or JSON response from Supervity API."""
    if not raw_text or not raw_text.strip():
        return "Workflow executed successfully, but returned an empty response."

    lines = raw_text.splitlines()
    parts = []
    is_error = False

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("event:"):
            evt = stripped[6:].strip()
            if evt in ["error", "quota-exceeded"]:
                is_error = True
        elif stripped.startswith("data:"):
            content_part = stripped[5:].strip()
            if content_part == "[DONE]":
                continue
            try:
                data = json.loads(content_part)
                if isinstance(data, dict):
                    msg = (
                        data.get("message") or data.get("error") or
                        data.get("text") or data.get("content") or
                        data.get("output") or data.get("response")
                    )
                    if msg:
                        parts.append(str(msg))
                    elif content_part:
                        parts.append(content_part)
                else:
                    parts.append(str(data))
            except Exception:
                parts.append(content_part)

    if parts:
        text = "\n".join(parts)
        return f"⚠️ {text}" if is_error else text

    try:
        data = json.loads(raw_text)
        if isinstance(data, dict):
            if data.get("error"):
                return f"Supervity Notice: {data.get('message') or data['error']}"
            for key in ["output", "response", "result", "message", "text", "content"]:
                if data.get(key):
                    return str(data[key])
            return json.dumps(data, indent=2)
    except Exception:
        pass

    return raw_text


# ─────────────────────────────────────────────────────────────────────────────
# Local fallback intelligence — queries the hackathon DB directly
# ─────────────────────────────────────────────────────────────────────────────

def _local_ai_response(message: str, db: Session, user_email: str) -> str:
    """
    Instant local AI response using the hackathon dataset.
    Handles common IT support queries without external API calls.
    Uses correct field names from the SQLAlchemy models.
    """
    msg_lower = message.lower()

    # ── Open / pending tickets ───────────────────────────────────────────────
    if any(k in msg_lower for k in ["open ticket", "pending ticket", "active ticket",
                                     "unresolved", "open issue"]):
        open_issues = (
            db.query(Issue)
            .filter(Issue.status.in_(["Open", "In Progress", "Pending"]))
            .order_by(Issue.ingested_at.desc())
            .limit(5)
            .all()
        )
        if not open_issues:
            return "✅ No open tickets found in the system right now."
        lines = [f"📋 **{len(open_issues)} recent open/pending tickets** (showing top 5):\n"]
        for t in open_issues:
            lines.append(f"- **{t.issue_key}** [{t.priority}] {t.summary} — *{t.status}*")
        return "\n".join(lines)

    # ── SLA / overdue ─────────────────────────────────────────────────────────
    if any(k in msg_lower for k in ["overdue", "sla breach", "sla", "breached", "late"]):
        breached = (
            db.query(Issue)
            .filter(Issue.status.in_(["Open", "In Progress", "Pending"]))
            .filter(Issue.time_to_resolution.ilike("%breached%"))
            .order_by(Issue.ingested_at.desc())
            .limit(5)
            .all()
        )
        if not breached:
            return "✅ No SLA breaches detected in open tickets."
        lines = [f"🚨 **{len(breached)} SLA-breached tickets** requiring attention:\n"]
        for t in breached:
            lines.append(f"- **{t.issue_key}** [{t.priority}] {t.summary}")
        return "\n".join(lines)

    # ── VIP issues ───────────────────────────────────────────────────────────
    if any(k in msg_lower for k in ["vip", "executive", "priority user"]):
        vip_users = (
            db.query(UserDirectory)
            .filter(UserDirectory.x_vip == True)  # noqa: E712
            .limit(10)
            .all()
        )
        vip_names = [u.display_name for u in vip_users]
        if not vip_names:
            return "No VIP users found in the directory."
        vip_issues = (
            db.query(Issue)
            .filter(Issue.reporter.in_(vip_names))
            .filter(Issue.status.in_(["Open", "In Progress", "Pending"]))
            .limit(5)
            .all()
        )
        if not vip_issues:
            return f"✅ No open tickets from VIP users ({', '.join(vip_names[:3])})."
        lines = [f"👑 **{len(vip_issues)} open VIP tickets**:\n"]
        for t in vip_issues:
            lines.append(f"- **{t.issue_key}** [{t.priority}] {t.summary} — *{t.reporter}*")
        return "\n".join(lines)

    # ── Ticket lookup by ID ──────────────────────────────────────────────────
    ticket_match = re.search(r'\b(ITSM|ISSUE|INC|CHG|REQ)[-\s]?(\d+)\b', message, re.IGNORECASE)
    if ticket_match:
        ticket_key = f"{ticket_match.group(1).upper()}-{ticket_match.group(2)}"
        issue = db.query(Issue).filter(Issue.issue_key == ticket_key).first()
        if issue:
            return (
                f"🎫 **{issue.issue_key}** — {issue.summary}\n\n"
                f"- **Status:** {issue.status}\n"
                f"- **Priority:** {issue.priority}\n"
                f"- **Reporter:** {issue.reporter or 'Unknown'}\n"
                f"- **Type:** {issue.issue_type or 'N/A'}\n"
                f"- **Created:** {issue.created or 'N/A'}\n"
                f"- **Description:** {(issue.description or '')[:200]}..."
            )
        return f"No ticket found with ID **{ticket_key}**."

    # ── Knowledge base search ─────────────────────────────────────────────────
    if any(k in msg_lower for k in ["knowledge", "kb", "article", "how to", "guide",
                                     "solution", "fix", "resolve", "workaround"]):
        keywords = [w for w in msg_lower.split() if len(w) > 3
                    and w not in {"help", "with", "that", "this", "know", "find", "articles"}]
        if keywords:
            from sqlalchemy import or_
            conditions = []
            for kw in keywords[:3]:
                conditions += [
                    KnowledgeBase.title.ilike(f"%{kw}%"),
                    KnowledgeBase.root_cause.ilike(f"%{kw}%"),
                    KnowledgeBase.workaround.ilike(f"%{kw}%"),
                ]
            query = db.query(KnowledgeBase).filter(or_(*conditions))
        else:
            query = db.query(KnowledgeBase)
        articles = query.limit(5).all()
        if articles:
            lines = [f"📚 **Found {len(articles)} knowledge base article(s):**\n"]
            for a in articles:
                lines.append(f"- **{a.article_id}** {a.title}")
                if a.workaround:
                    lines.append(f"  _Workaround: {a.workaround[:150]}..._")
            return "\n".join(lines)
        # No keyword match — show all available articles instead
        all_articles = db.query(KnowledgeBase).limit(10).all()
        if all_articles:
            lines = ["No articles matched that query. Here's what's available in the KB:\n"]
            for a in all_articles:
                lines.append(f"- **{a.article_id}** {a.title}")
            return "\n".join(lines)
        return "The knowledge base is currently empty."

    # ── Workbench / pending approvals ────────────────────────────────────────
    if any(k in msg_lower for k in ["workbench", "approval", "approve", "pending approval",
                                     "queue", "review"]):
        pending = (
            db.query(WorkbenchItem)
            .filter(WorkbenchItem.status == "pending_approval")
            .count()
        )
        if pending == 0:
            return "✅ Your Workbench queue is empty — no items pending approval."
        return (
            f"🔔 You have **{pending} item(s)** pending approval in your Workbench.\n\n"
            f"Visit [Workbench](/workbench) to review and approve or reject them."
        )

    # ── CSAT summary ─────────────────────────────────────────────────────────
    if any(k in msg_lower for k in ["csat", "satisfaction", "rating", "score", "feedback"]):
        surveys = db.query(CSATSurvey).all()
        if not surveys:
            return "No CSAT survey data available yet."
        scores = [s.score for s in surveys if s.score is not None]
        avg = sum(scores) / len(scores) if scores else 0
        return (
            f"⭐ **CSAT Summary** ({len(surveys)} responses):\n\n"
            f"- Average Score: **{avg:.1f}/5**\n"
            f"- Total Responses: **{len(surveys)}**\n"
            f"- Positive (≥4): **{sum(1 for s in scores if s >= 4)}**\n"
            f"- Negative (<3): **{sum(1 for s in scores if s < 3)}**"
        )

    # ── Stats / summary ──────────────────────────────────────────────────────
    if any(k in msg_lower for k in ["summary", "dashboard", "stats", "statistic",
                                     "overview", "report", "count", "how many"]):
        total = db.query(Issue).count()
        open_count = (
            db.query(Issue)
            .filter(Issue.status.in_(["Open", "In Progress", "Pending"]))
            .count()
        )
        resolved = db.query(Issue).filter(Issue.status == "Resolved").count()
        kb_count = db.query(KnowledgeBase).count()
        pending_wb = (
            db.query(WorkbenchItem)
            .filter(WorkbenchItem.status == "pending_approval")
            .count()
        )
        return (
            f"📊 **AutoPilot Dashboard Summary**\n\n"
            f"| Metric | Count |\n"
            f"|--------|-------|\n"
            f"| Total Tickets | {total} |\n"
            f"| Open / In Progress | {open_count} |\n"
            f"| Resolved | {resolved} |\n"
            f"| KB Articles | {kb_count} |\n"
            f"| Workbench Pending | {pending_wb} |"
        )

    # ── Default helpful response ──────────────────────────────────────────────
    return (
        "👋 Hi! I'm your **AutoPilot AI Assistant**. I can help you with:\n\n"
        "- 📋 **View open/pending tickets** — *\"Show me open tickets\"*\n"
        "- 🚨 **SLA alerts** — *\"Any SLA breaches?\"*\n"
        "- 👑 **VIP issues** — *\"Show VIP user tickets\"*\n"
        "- 🎫 **Ticket lookup** — *\"Tell me about ITSM-2013\"*\n"
        "- 📚 **Knowledge base** — *\"How to resolve login issues?\"*\n"
        "- 📊 **Dashboard summary** — *\"Give me a summary\"*\n"
        "- 🔔 **Workbench queue** — *\"Any pending approvals?\"*\n\n"
        "What would you like to know?"
    )


# ─────────────────────────────────────────────────────────────────────────────
# Chat endpoint
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/chat", response_model=AIChatResponse)
async def ai_chat(
    payload: AIChatRequest,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    AI Manager chat endpoint.

    Flow:
      1. Try Supervity cloud workflow (15s timeout) if API key + workflow ID are set.
      2. On timeout/error OR if keys not configured → instant local DB-powered response.
    """
    api_url = _env(
        "SUPERVITY_API_URL",
        "https://auto-workflow-api.supervity.ai/api/v1/workflow-runs/execute/stream",
    )
    workflow_id = _env("SUPERVITY_WORKFLOW_ID", "")
    api_key = _env("SUPERVITY_API_KEY", "")
    active_org = _env("SUPERVITY_ACTIVE_ORG", "")
    active_team = _env("SUPERVITY_ACTIVE_TEAM", "")
    team_key = _env("SUPERVITY_TEAM_KEY", "")
    user_timezone = _env("SUPERVITY_USER_TIMEZONE", "Asia/Kuala_Lumpur")

    user_email = current_user.get("email") or payload.reporter_email or "user@example.com"
    skip_supervity = not api_key or not workflow_id

    log.info(f"AI chat: user={user_email}, supervity_skip={skip_supervity}, msg='{payload.message[:60]}'")

    # ── Supervity fast path (only if both API key and workflow ID are configured) ─
    if not skip_supervity:
        headers = {
            "Authorization": f"Bearer {api_key}",
            "x-source": "external",
            "x-user-timezone": user_timezone,
        }
        if active_org:
            headers["x-active-org"] = active_org
        if active_team:
            headers["x-active-team"] = active_team
        if team_key:
            headers["x-teamKey"] = team_key

        form_fields = {
            "workflowId": (None, workflow_id),
            "inputs[issue_key]": (None, payload.issue_key or ""),
            "inputs[ticket_description]": (None, payload.message),
            "inputs[reporter_email]": (None, user_email),
            "inputs[inactive_days_threshold]": (None, str(payload.inactive_days_threshold)),
            "inputs[sla_threshold_hours]": (None, str(payload.sla_threshold_hours)),
            "inputs[it_team_slack]": (None, payload.it_team_slack or "#it-support"),
        }

        try:
            # Short timeout: if Supervity has a Human Approval node it will hang.
            # We catch that and fall through to local response.
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.post(api_url, headers=headers, files=form_fields)
                if response.status_code == 200:
                    ai_message = parse_supervity_output(response.text)
                    if ai_message and "empty" not in ai_message.lower():
                        log.info("Supervity responded successfully.")
                        return AIChatResponse(
                            response=ai_message,
                            status="success",
                            workflow_id=workflow_id,
                        )
                else:
                    log.warning(f"Supervity HTTP {response.status_code} — falling back to local.")
        except httpx.TimeoutException:
            log.warning("Supervity workflow timed out — using local AI response.")
        except httpx.RequestError as err:
            log.warning(f"Supervity unreachable ({err}) — using local AI response.")

    # ── Local fallback — always instant ──────────────────────────────────────
    local_response = _local_ai_response(payload.message, db, user_email)
    log.info("Returning local AI response.")
    return AIChatResponse(
        response=local_response,
        status="success",
        workflow_id=workflow_id or "local",
    )
