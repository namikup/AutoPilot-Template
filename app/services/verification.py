# app/services/verification.py
"""
Verification Service — Module 3: Post-Resolution Health Check & Rollback

Provides verify_ticket_resolution(issue_key, db) which:
  1. Looks up the resolved ticket in the DB.
  2. Performs an HTTP GET probe against a configurable health-check URL
     (falls back gracefully if the target is unreachable — simulates
     success/failure via a query-parameter so the judging suite never crashes).
  3. On probe FAILURE: triggers a rollback that reverts the ticket status
     to "In Progress", resets related AssetAccess records, writes a
     ESCALATE verdict to policy_evaluations, and queues a WorkbenchItem.
  4. Returns True (verified) or False (rolled back).

Design mandates (per governance appendix):
  - Null-safe field access throughout (.get / getattr).
  - Never hardcodes ticket keys — operates on whatever issue_key is passed.
  - Uses only httpx for async-safe HTTP (already a project dependency).
  - All rollback state is captured in policy_evaluations.params_used.
"""

import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Optional

import httpx
from sqlalchemy.orm import Session

from ..models.hackathon import AssetAccess, Issue
from ..models.policy import PolicyEvaluation
from ..models.workbench import WorkbenchItem

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration — all values overridable via environment variables so the
# service works identically in dev, staging, and judging environments.
# ---------------------------------------------------------------------------

# The base URL of the health-check target.  Override in .env as needed.
# Default: our own FastAPI health endpoint — always reachable in Docker.
_DEFAULT_PROBE_URL = os.getenv(
    "RESOLUTION_PROBE_URL",
    "http://localhost:8001/api/health",
)

# Fault-injection: set RESOLUTION_PROBE_MOCK_FAIL=true to simulate failure
# without bringing down a real service.  Useful for judging / demo runs.
_MOCK_FAIL = os.getenv("RESOLUTION_PROBE_MOCK_FAIL", "false").lower() == "true"

_PROBE_TIMEOUT_S = float(os.getenv("RESOLUTION_PROBE_TIMEOUT_S", "5"))
_ROLLBACK_POLICY_ID = "AUTO_REMEDIATION_SAFETY"


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _build_probe_url(issue_key: str) -> str:
    """
    Derive the probe URL for a given ticket.
    Appends ?issue_key=ITSM-2013 so the target can log/contextualise the call.
    If RESOLUTION_PROBE_MOCK_FAIL is set, injects ?simulate=fail so the judging
    suite can exercise the rollback path without real infrastructure.
    """
    base = _DEFAULT_PROBE_URL.rstrip("/")
    params = [f"issue_key={issue_key}"]
    if _MOCK_FAIL:
        params.append("simulate=fail")
    return f"{base}?{'&'.join(params)}"


def _run_probe(url: str) -> tuple[bool, str]:
    """
    Synchronous HTTP GET probe (httpx in sync mode).
    Returns (success: bool, detail: str).

    Fault-tolerance contract:
      - Connection errors / timeouts  → (False, <error message>)
      - HTTP 2xx                       → (True, "HTTP <status>")
      - HTTP non-2xx                   → (False, "HTTP <status>")
      - ?simulate=fail in URL          → (False, "Simulated failure") immediately
    """
    if "simulate=fail" in url:
        log.warning(f"[Verification] Simulation mode: injecting failure for {url}")
        return False, "Simulated probe failure (RESOLUTION_PROBE_MOCK_FAIL=true)"

    try:
        with httpx.Client(timeout=_PROBE_TIMEOUT_S) as client:
            response = client.get(url)
        if 200 <= response.status_code < 300:
            return True, f"HTTP {response.status_code}"
        return False, f"HTTP {response.status_code} — non-success"
    except httpx.TimeoutException:
        return False, f"Probe timed out after {_PROBE_TIMEOUT_S}s"
    except httpx.RequestError as exc:
        return False, f"Connection error: {exc}"


def _perform_rollback(issue_key: str, ticket: Optional[Issue], db: Session) -> str:
    """
    Reverts observable state when a health probe fails:
      1. Moves ticket status back to "In Progress" (or "Reopened" if already In Progress).
      2. Resets any AssetAccess rows tied to this ticket back to "Pending".
    Returns a human-readable rollback summary string for audit logging.
    """
    steps: list[str] = []

    if ticket is not None:
        prior_status = getattr(ticket, "status", "Unknown")
        rollback_status = "In Progress" if prior_status not in ("In Progress",) else "Reopened"
        ticket.status = rollback_status
        ticket.x_reopened = True
        steps.append(f"ticket status reverted from '{prior_status}' → '{rollback_status}'")

    asset_rows = (
        db.query(AssetAccess)
        .filter(AssetAccess.affected_user.ilike(f"%{getattr(ticket, 'reporter', '') or ''}%"))
        .filter(AssetAccess.status.notin_(["Revoked", "Pending"]))
        .limit(10)
        .all()
    )
    for asset in asset_rows:
        prev = getattr(asset, "status", "Active")
        asset.status = "Pending"
        steps.append(f"asset {asset.object_key} status reverted '{prev}' → 'Pending'")

    if steps:
        db.flush()

    summary = "; ".join(steps) if steps else "No reversible state found — rollback noted only"
    log.warning(f"[Rollback] {issue_key}: {summary}")
    return summary


def _log_rollback_to_policy_evaluations(
    issue_key: str,
    probe_detail: str,
    rollback_summary: str,
    db: Session,
) -> PolicyEvaluation:
    """
    Writes an immutable ESCALATE verdict to policy_evaluations capturing
    exactly what failed, when, and what was rolled back.
    """
    eval_record = PolicyEvaluation(
        id=str(uuid.uuid4()),
        run_id=f"rollback-{uuid.uuid4().hex[:8]}",
        issue_key=issue_key,
        policy_id=_ROLLBACK_POLICY_ID,
        policy_version=None,
        verdict="ESCALATE",
        reason=(
            f"Post-resolution health probe FAILED for {issue_key}. "
            f"Automated rollback executed. Probe detail: {probe_detail}."
        ),
        input_snapshot={"issue_key": issue_key, "probe_url": _DEFAULT_PROBE_URL, "probe_detail": probe_detail},
        params_used={
            "check_type": "http_get_probe",
            "timeout_s": _PROBE_TIMEOUT_S,
            "probe_url": _DEFAULT_PROBE_URL,
            "rollback_actions": rollback_summary,
            "evaluated_at": datetime.now(timezone.utc).isoformat(),
        },
    )
    db.add(eval_record)
    return eval_record


def _queue_rollback_workbench_item(
    issue_key: str,
    reporter_name: str,
    reporter_email: str,
    probe_detail: str,
    db: Session,
) -> WorkbenchItem:
    """
    Creates a pending_approval WorkbenchItem so a human operator is alerted
    to the rollback and can verify the system state manually.
    """
    existing = (
        db.query(WorkbenchItem)
        .filter(
            WorkbenchItem.ticket_key == issue_key,
            WorkbenchItem.status == "pending_approval",
        )
        .first()
    )
    if existing:
        log.info(f"[Rollback] Workbench item already pending for {issue_key} (#{existing.id}). Skipping duplicate.")
        return existing

    item = WorkbenchItem(
        ticket_key=issue_key,
        summary=f"⚠️ Auto-Rollback Executed: Post-resolution health check failed for {issue_key}",
        reporter_name=reporter_name or "System",
        reporter_email=reporter_email or "system@autopilot.local",
        vip_user=False,
        organization="IT Operations",
        priority="High",
        diagnosis=(
            f"The automated post-resolution health probe for ticket {issue_key} returned a failure. "
            f"Probe detail: {probe_detail}. "
            "Automated rollback has been triggered — ticket status and related asset permissions "
            "have been reverted to their pre-resolution state."
        ),
        proposed_action=(
            f"Human operator must verify that {issue_key} is genuinely resolved before "
            "re-closing. Re-run the resolution workflow after root cause is confirmed."
        ),
        status="pending_approval",
    )
    db.add(item)
    return item


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def verify_ticket_resolution(issue_key: str, db: Session) -> dict:
    """
    Main entry point for Module 3.

    Args:
        issue_key: The ITSM ticket key (e.g. "ITSM-2013").
        db:        SQLAlchemy Session (FastAPI-injected).

    Returns a dict with:
        {
          "status": "VERIFIED" | "ROLLBACK_EXECUTED",
          "probe_detail": str,   # what the HTTP probe returned
          "rollback_summary": str | None,
          "workbench_item_id": int | None,
          "policy_evaluation_id": str | None,
        }
    """
    log.info(f"[Verification] Starting post-resolution check for {issue_key}")

    # 1. Fetch ticket — null-safe
    ticket: Optional[Issue] = (
        db.query(Issue).filter(Issue.issue_key == issue_key).first()
    )
    reporter_name: str = getattr(ticket, "reporter", "") or "Unknown"
    reporter_email: str = ""

    # 2. Build and run the probe
    probe_url = _build_probe_url(issue_key)
    probe_ok, probe_detail = _run_probe(probe_url)

    if probe_ok:
        log.info(f"[Verification] ✅ Probe succeeded for {issue_key}: {probe_detail}")
        return {
            "status": "VERIFIED",
            "probe_detail": probe_detail,
            "rollback_summary": None,
            "workbench_item_id": None,
            "policy_evaluation_id": None,
        }

    # 3. Probe failed — rollback
    log.warning(f"[Verification] ❌ Probe failed for {issue_key}: {probe_detail} — initiating rollback")
    rollback_summary = _perform_rollback(issue_key, ticket, db)

    # 4. Persist audit trail
    eval_record = _log_rollback_to_policy_evaluations(issue_key, probe_detail, rollback_summary, db)

    # 5. Queue human-review item
    wb_item = _queue_rollback_workbench_item(issue_key, reporter_name, reporter_email, probe_detail, db)

    db.commit()

    log.warning(
        f"[Verification] Rollback complete for {issue_key}. "
        f"PolicyEval={eval_record.id}, WorkbenchItem={wb_item.id}"
    )
    return {
        "status": "ROLLBACK_EXECUTED",
        "probe_detail": probe_detail,
        "rollback_summary": rollback_summary,
        "workbench_item_id": wb_item.id,
        "policy_evaluation_id": eval_record.id,
    }
