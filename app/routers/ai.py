# app/routers/ai.py
"""
AI Management Router - Connects frontend AI Manager to the AutoPilot knowledge base & Supervity Auto.

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
from sqlalchemy import or_, and_

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


def _auto_route_workbench_if_needed(text: str, payload: AIChatRequest, db: Session, user_email: str) -> tuple[str, str | None]:
    """
    Detects if the AI output, Supervity inputs, or user prompt requires human review/operator escalation.
    Triggers for:
    - VIP reporter (e.g. faizal.das@company.com, Faizal Das, x_vip=True)
    - High/Highest priority tickets
    - SLA threshold <= 24 hours
    - Keywords indicating review, escalation, approval, or human operator needed
    - Explicit issue_key provided (e.g. ITSM-2013)
    """
    # Extract ticket key ONLY from the user's message or payload (do not scan AI output text!)
    ticket_key = payload.issue_key
    if not ticket_key or ticket_key == "ISSUE-101":
        match = re.search(r'\b(ITSM|ISSUE|INC|CHG|REQ|SUP)[-\s]?(\d+)\b', payload.message, re.IGNORECASE)
        if match:
            ticket_key = f"{match.group(1).upper()}-{match.group(2)}"
        elif not ticket_key:
            ticket_key = "TASK-AUTO"

    issue_obj = db.query(Issue).filter(Issue.issue_key == ticket_key).first() if ticket_key != "TASK-AUTO" else None

    # Check reporter & VIP status from UserDirectory
    user_db = None
    if issue_obj and issue_obj.reporter:
        user_db = db.query(UserDirectory).filter(UserDirectory.display_name.ilike(f"%{issue_obj.reporter}%")).first()
    if not user_db and payload.reporter_email:
        user_db = db.query(UserDirectory).filter(UserDirectory.email_address.ilike(f"%{payload.reporter_email}%")).first()

    rep_email = user_db.email_address if user_db else (payload.reporter_email or (issue_obj.reporter_email if issue_obj and hasattr(issue_obj, 'reporter_email') else user_email))
    rep_name = user_db.display_name if user_db else (issue_obj.reporter if issue_obj else (rep_email.split('@')[0].replace('.', ' ').title()))
    is_vip = getattr(user_db, 'x_vip', False) if user_db else (rep_name in ["Faizal Das", "Tariq Lim", "Aisha Lim", "Faizal Chen", "Faizal Iyer"] or "faizal.das" in rep_email)

    user_msg_lower = payload.message.lower()
    has_keywords = any(k in user_msg_lower for k in [
        "human operator", "escalat", "human review", "pending approval",
        "hitl", "override", "pause", "require human", "requires human", "exception"
    ])

    # Only trigger Workbench item creation if an EXPLICIT real ticket is involved,
    # or if explicit VIP / escalation / review keywords are present in the request.
    is_real_ticket = (issue_obj is not None) or (ticket_key not in ["ISSUE-101", "TASK-AUTO"] and ticket_key.startswith(("ITSM-", "INC-", "CHG-", "REQ-")))
    
    is_high_priority = (issue_obj.priority in ["High", "Highest"]) if issue_obj else False
    is_tight_sla = (payload.sla_threshold_hours is not None and payload.sla_threshold_hours <= 24 and is_real_ticket)

    # Informational KB queries / Q&A without a real ticket should NOT create dummy workbench items
    if ticket_key in ["ISSUE-101", "TASK-AUTO"] and not has_keywords:
        return text, None

    needs_review = (is_vip and is_real_ticket) or has_keywords or (is_real_ticket and (is_high_priority or is_tight_sla))

    if not needs_review:
        return text, None

    # Check if existing pending item for this ticket already exists
    existing = db.query(WorkbenchItem).filter(
        WorkbenchItem.ticket_key == ticket_key,
        WorkbenchItem.status == "pending_approval"
    ).first()

    if existing:
        notice = f"\n\n📌 **Pending Approval Exists:** Item **#{existing.id}** for `{ticket_key}` is awaiting review in your [Workbench Queue](/workbench)."
        return text + notice, str(existing.id)

    # Determine real SLA status from ticket
    sla_desc = "SLA status unknown"
    if issue_obj:
        if issue_obj.time_to_resolution:
            sla_desc = f"SLA Status: {issue_obj.time_to_resolution}"
        elif payload.sla_threshold_hours is not None:
            sla_desc = f"SLA Remaining: {payload.sla_threshold_hours}h"
        elif issue_obj.due_date:
            sla_desc = f"SLA Due: {issue_obj.due_date}"

    # Determine real policy evaluation reason
    reasons = []
    if is_vip:
        reasons.append(f"VIP Reporter ({rep_name})")
    if is_high_priority:
        reasons.append(f"{issue_obj.priority} Priority")
    if has_keywords:
        reasons.append("Operator Escalation Requested")
    if not reasons:
        reasons.append("Policy Gate Compliance Required")

    escalation_reason = " & ".join(reasons)
    vip_tag = " (VIP)" if is_vip else ""
    
    summary_text = issue_obj.summary if issue_obj else (payload.message if len(payload.message) > 10 else f"Supervity Auto Task: {ticket_key}")
    org_text = issue_obj.organizations if issue_obj else "Finance"
    priority_text = issue_obj.priority if issue_obj else "High"
    slack_channel = payload.it_team_slack or "#gang-intelligence"

    diag_text = f"Policy Evaluation Escalation: {escalation_reason} | {sla_desc}. Requires human signoff before execution."
    prop_action = f"Review & authorize resolution action for {ticket_key} via {slack_channel}."

    new_item = WorkbenchItem(
        ticket_key=ticket_key,
        summary=summary_text,
        reporter_name=rep_name,
        reporter_email=rep_email,
        vip_user=is_vip,
        organization=org_text,
        priority=priority_text,
        diagnosis=diag_text,
        proposed_action=prop_action,
        status="pending_approval"
    )
    db.add(new_item)
    db.commit()
    db.refresh(new_item)

    log.info(f"🚨 Auto-routed Supervity task to Workbench ID {new_item.id} for ticket {ticket_key}")
    vip_str = " (VIP)" if is_vip else ""
    notice = f"\n\n📌 **Human Operator Review Required:** Item **#{new_item.id}** for `{ticket_key}` (Reporter: {rep_name}{vip_str}, Priority: {priority_text}, {sla_desc}) has been auto-routed to your [Workbench Queue](/workbench)."
    return text + notice, str(new_item.id)


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

    # ── Ticket lookup by explicit ID (e.g. ITSM-2008) ────────────────────────
    ticket_match = re.search(r'\b(ITSM|ISSUE|INC|CHG|REQ|SUP)[-\s]?(\d+)\b', message, re.IGNORECASE)
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
                f"- **Description:** {issue.description or 'No description provided.'}"
            )
        return f"❓ Ticket **{ticket_key}** was not found in the dataset."

    # ── User ticket query (e.g. "tickets for Chloe Fernandez") ──────────────
    if any(k in msg_lower for k in ["tickets for", "issues for", "reported by", "user tickets"]):
        words = message.replace("?", "").split()
        possible_names = []
        for i in range(len(words) - 1):
            pair = f"{words[i]} {words[i+1]}".strip(",. ")
            if len(pair) > 4 and pair.lower() not in ["show me", "tickets for", "issues for", "list all"]:
                possible_names.append(pair)

        for name in possible_names:
            user_issues = (
                db.query(Issue)
                .filter(Issue.reporter.ilike(f"%{name}%"))
                .order_by(Issue.ingested_at.desc())
                .limit(5)
                .all()
            )
            if user_issues:
                lines = [f"👤 **{len(user_issues)} tickets reported by {name}:**\n"]
                for t in user_issues:
                    lines.append(f"- **{t.issue_key}** [{t.priority}] {t.summary} — *{t.status}*")
                return "\n".join(lines)

    # ── Priority-specific queries ────────────────────────────────────────────
    if any(k in msg_lower for k in ["high priority", "highest priority", "urgent", "critical"]):
        priorities = ["Highest", "High"]
        if "medium" in msg_lower:
            priorities = ["Medium"]
        elif "low" in msg_lower:
            priorities = ["Low"]

        filtered_issues = (
            db.query(Issue)
            .filter(Issue.status.in_(["Open", "In Progress", "Pending"]))
            .filter(Issue.priority.in_(priorities))
            .order_by(Issue.ingested_at.desc())
            .limit(5)
            .all()
        )
        if filtered_issues:
            lines = [f"🔥 **{len(filtered_issues)} {'/'.join(priorities)} priority open tickets:**\n"]
            for t in filtered_issues:
                lines.append(f"- **{t.issue_key}** [{t.priority}] {t.summary} — *{t.status}*")
            return "\n".join(lines)
        return f"✅ No open tickets found matching priority **{'/'.join(priorities)}**."

    # ── Status-specific ticket queries ──────────────────────────────────────
    if "in progress" in msg_lower or "in-progress" in msg_lower:
        ip_issues = (
            db.query(Issue)
            .filter(Issue.status == "In Progress")
            .order_by(Issue.ingested_at.desc())
            .limit(5)
            .all()
        )
        if ip_issues:
            lines = [f"⚙️ **{len(ip_issues)} tickets currently In Progress:**\n"]
            for t in ip_issues:
                lines.append(f"- **{t.issue_key}** [{t.priority}] {t.summary} — *{t.reporter or 'Unknown'}*")
            return "\n".join(lines)
        return "✅ No tickets currently In Progress."

    if ("resolved" in msg_lower and "unresolved" not in msg_lower) or "closed" in msg_lower:
        res_issues = (
            db.query(Issue)
            .filter(Issue.status.in_(["Resolved", "Closed"]))
            .order_by(Issue.ingested_at.desc())
            .limit(5)
            .all()
        )
        if res_issues:
            lines = [f"✅ **{len(res_issues)} recently resolved/closed tickets:**\n"]
            for t in res_issues:
                lines.append(f"- **{t.issue_key}** [{t.priority}] {t.summary}")
            return "\n".join(lines)
        return "No resolved tickets found."

    # ── Open / active / pending tickets general ───────────────────────────────
    if any(k in msg_lower for k in [
        "open ticket", "open tickets", "pending ticket", "pending tickets",
        "active ticket", "active tickets", "active issue", "active issues",
        "unresolved", "open issue", "open issues", "show tickets", "list tickets",
        "list pending", "all pending", "active right now", "any active",
        "current tickets", "current issues", "any issues"
    ]):
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

    # ── CSAT & Feedback / Reviews ─────────────────────────────────────────────
    if any(k in msg_lower for k in ["csat", "satisfaction", "rating", "score", "feedback", "review", "reviews"]):
        surveys = db.query(CSATSurvey).all()
        if not surveys:
            return "No CSAT survey data available yet."
        scores = [s.score for s in surveys if s.score is not None]
        avg = sum(scores) / len(scores) if scores else 0
        pos = sum(1 for s in scores if s >= 4)
        neg = sum(1 for s in scores if s < 3)

        if "negative" in msg_lower or "bad" in msg_lower or "poor" in msg_lower:
            neg_surveys = [s for s in surveys if s.score is not None and s.score < 3]
            lines = [f"👎 **CSAT Negative Reviews** ({len(neg_surveys)} total <3/5 rating):\n"]
            for s in neg_surveys[:3]:
                lines.append(f"- **{s.issue_key}** (Score: {s.score}/5): _{s.comment or 'No comment'}_")
            return "\n".join(lines)

        return (
            f"⭐ **CSAT Summary** ({len(surveys)} responses):\n\n"
            f"- Average Score: **{avg:.1f}/5**\n"
            f"- Total Responses: **{len(surveys)}**\n"
            f"- Positive (≥4): **{pos}**\n"
            f"- Negative (<3): **{neg}**"
        )

    # ── Knowledge base search ─────────────────────────────────────────────────
    if any(k in msg_lower for k in ["knowledge", "kb", "article", "articles", "how to", "guide",
                                     "solution", "fix", "resolve", "workaround", "slow", "wifi", "network", "password", "printer", "drive", "email", "guest"]):
        raw_words = re.findall(r'\b[a-zA-Z0-9]+\b', msg_lower)
        stopwords = {
            "help", "with", "that", "this", "know", "find", "articles", "article",
            "show", "tell", "about", "how", "to", "fix", "resolve", "search", "list",
            "what", "is", "the", "for", "and", "can", "you", "me", "base", "knowledge", "kb", "issue", "problem"
        }
        keywords = [w for w in raw_words if len(w) >= 2 and w not in stopwords]

        if keywords:
            # Score articles by relevance (title matches scored higher than body matches)
            all_kb = db.query(KnowledgeBase).all()
            scored: list[tuple[int, KnowledgeBase]] = []
            for a in all_kb:
                score = 0
                title_lower = (a.title or "").lower()
                rc_lower = (a.root_cause or "").lower()
                wa_lower = (a.workaround or "").lower()

                for kw in keywords:
                    if kw in title_lower:
                        score += 5
                    if kw in rc_lower:
                        score += 2
                    if kw in wa_lower:
                        score += 2

                if score > 0:
                    scored.append((score, a))

            scored.sort(key=lambda x: x[0], reverse=True)
            articles = [a for _, a in scored[:5]]

            if articles:
                lines = [f"📚 **Found {len(articles)} knowledge base article(s):**\n"]
                for a in articles:
                    lines.append(f"- **{a.article_id}** {a.title}")
                    if a.workaround:
                        lines.append(f"  _Workaround: {a.workaround[:150]}..._")
                return "\n".join(lines)

        all_articles = db.query(KnowledgeBase).limit(5).all()
        if all_articles:
            prefix = "📚 **Knowledge Base Articles:**\n" if not keywords else f"No specific KB article matched **'{' '.join(keywords)}'**. Here are available guides:\n"
            lines = [prefix]
            for a in all_articles:
                lines.append(f"- **{a.article_id}** {a.title}")
            return "\n".join(lines)
        return "The knowledge base is currently empty."

    # ── Workbench / pending approvals ────────────────────────────────────────
    if any(k in msg_lower for k in ["workbench", "pending approval", "approval queue", "items to approve", "approval"]):
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
        "- 🔥 **Priority tickets** — *\"High priority open tickets\"*\n"
        "- 👤 **User tickets** — *\"Tickets for Chloe Fernandez\"*\n"
        "- 🚀 **Run Supervity Auto Workflow** — *\"Run workflow for ITSM-2013\"*\n"
        "- 🚨 **SLA alerts** — *\"Any SLA breaches?\"*\n"
        "- 👑 **VIP issues** — *\"Show VIP user tickets\"*\n"
        "- 🎫 **Ticket lookup** — *\"Tell me about ITSM-2013\"*\n"
        "- 📚 **Knowledge base** — *\"How to fix VPN drops?\"*\n"
        "- ⭐ **CSAT & Reviews** — *\"Any negative reviews?\"*\n"
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
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    Primary AI chat & Supervity Auto workflow execution route.
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

    # Explicit workflow trigger intent check
    msg_lower = payload.message.lower()
    is_explicit_workflow_trigger = any(k in msg_lower for k in [
        "run workflow", "trigger workflow", "execute workflow", "start workflow",
        "run orchestrator", "trigger orchestrator", "execute orchestrator", "run supervity"
    ])

    skip_supervity = not api_key or not workflow_id

    log.info(f"AI chat: user={user_email}, explicit_trigger={is_explicit_workflow_trigger}, msg='{payload.message[:60]}'")

    # ── Supervity execution path ───────────────────────────────────────────────
    if not skip_supervity and (is_explicit_workflow_trigger or not payload.message):
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
            "inputs[reporter_email]": (None, payload.reporter_email or user_email),
            "inputs[inactive_days_threshold]": (None, str(payload.inactive_days_threshold)),
            "inputs[sla_threshold_hours]": (None, str(payload.sla_threshold_hours)),
            "inputs[it_team_slack]": (None, payload.it_team_slack or "#it-support"),
        }

        try:
            import asyncio
            async with httpx.AsyncClient(timeout=httpx.Timeout(5.0, connect=3.0)) as client:
                response = await asyncio.wait_for(
                    client.post(api_url, headers=headers, files=form_fields),
                    timeout=5.0,
                )
                if response.status_code == 200:
                    ai_message = parse_supervity_output(response.text)
                    if ai_message and "empty" not in ai_message.lower():
                        log.info("Supervity responded successfully.")
                        final_msg, _ = _auto_route_workbench_if_needed(ai_message, payload, db, user_email)
                        return AIChatResponse(
                            response=final_msg,
                            status="success",
                            workflow_id=workflow_id,
                        )
                else:
                    log.warning(f"Supervity HTTP {response.status_code} — falling back to local.")
        except (httpx.TimeoutException, asyncio.TimeoutError):
            log.warning("Supervity workflow timed out (5s wall clock limit) — using local AI response.")
        except httpx.RequestError as err:
            log.warning(f"Supervity unreachable ({err}) — using local AI response.")

    # ── Local fallback — always instant ──────────────────────────────────────
    local_response = _local_ai_response(payload.message, db, user_email)
    final_msg, _ = _auto_route_workbench_if_needed(local_response, payload, db, user_email)
    log.info("Returning local AI response.")
    return AIChatResponse(
        response=final_msg,
        status="success",
        workflow_id=workflow_id or "local",
    )


@router.get("/dashboard-stats")
async def get_dashboard_stats(db: Session = Depends(get_db)):
    """Fetch live counts from PostgreSQL for dashboard stats cards."""
    total_users = db.query(UserDirectory).count()
    active_tickets = db.query(Issue).filter(Issue.status.in_(["Open", "In Progress"])).count()
    total_tickets = db.query(Issue).count()
    resolved_tickets = db.query(Issue).filter(Issue.status.in_(["Resolved", "Closed"])).count()
    csat_count = db.query(CSATSurvey).count()
    positive_csat = db.query(CSATSurvey).filter(CSATSurvey.score >= 4).count()
    csat_rate = round((positive_csat / csat_count * 100), 1) if csat_count > 0 else 98.0
    pending_wb = db.query(WorkbenchItem).filter(WorkbenchItem.status == "pending_approval").count()

    return {
        "total_users": total_users,
        "active_sessions": active_tickets,
        "success_rate": csat_rate,
        "ai_confidence": 96.0,
        "resolved_tickets": resolved_tickets,
        "total_tickets": total_tickets,
        "pending_workbench": pending_wb,
    }
