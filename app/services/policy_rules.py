# app/services/policy_rules.py
"""
Policy Rules Engine — pure evaluation functions for AI governance policies.

Each rule takes the current request context (`req`) and the policy's
editable `params` (as stored on the `Policy.params` JSONB column) and
returns a (verdict, reason) tuple:

    verdict: "ALLOW" | "ESCALATE" | "DENY"
    reason:  a human-readable sentence, shown to a reviewer in the
             Workbench and persisted on PolicyEvaluation.reason for audit.

Design principle — fail safe, never fail loud:
    A rule must NEVER raise on a missing key. If a value needed to make
    the actual ALLOW/ESCALATE decision is absent, the rule escalates and
    says so in the reason. It never falls back to a guessed value that
    could silently produce an unsafe ALLOW. Purely descriptive fields
    (used only to make the reason readable) degrade gracefully instead
    of forcing an escalation.

Usage:
    from app.services.policy_rules import RULES

    rule_fn = RULES[policy.id]
    verdict, reason = rule_fn(req, policy.params)
"""

from typing import Callable, Optional

RuleFn = Callable[[dict, dict], tuple[str, str]]


def _is_empty(value) -> bool:
    """
    True for None, blank strings, and empty collections.
    False for 0, False, and any other present-but-falsy value —
    those are real values, not missing data.
    """
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, (list, dict, tuple, set)):
        return len(value) == 0
    return False


def _round(value):
    """Round floats to 2 decimal places for display; leave other types untouched."""
    if isinstance(value, float):
        return round(value, 2)
    return value


# =============================================================================
# 1. DATA_COMPLETENESS
# =============================================================================


def data_completeness(req: dict, params: dict) -> tuple[str, str]:
    """Block action when required ticket fields are missing."""
    required_fields = params.get("required_fields") or []
    on_missing = params.get("on_missing") or "ESCALATE"

    for field in required_fields:
        if _is_empty(req.get(field)):
            return on_missing, f"Required field {field} is missing; cannot proceed safely"

    return "ALLOW", "All required fields are present"


# =============================================================================
# 2. CHANGE_APPROVAL_GATE
# =============================================================================


def change_approval_gate(req: dict, params: dict) -> tuple[str, str]:
    """Route high-risk or CAB-flagged changes and rollbacks to a human."""
    block_risk_levels = params.get("block_risk_levels") or []

    if req.get("change_required"):
        risk = req.get("risk")
        if risk is None:
            return "ESCALATE", "Change risk level is missing; cannot verify approval requirements"
        if risk in block_risk_levels:
            change_ref = req.get("change_id") or req.get("ticket_key") or "This change"
            return "ESCALATE", f"Change {change_ref} is {risk} risk and requires CAB approval"

    if req.get("cab_approval_required") and params.get("require_cab_when_flagged"):
        return "ESCALATE", "CAB approval required before touching production"

    if req.get("is_rollback") and params.get("rollback_requires_approval"):
        return "ESCALATE", "Rollback requires human approval"

    return "ALLOW", "No change control gates were triggered"


# =============================================================================
# 3. AUTO_REMEDIATION_SAFETY
# =============================================================================


def auto_remediation_safety(req: dict, params: dict) -> tuple[str, str]:
    """Only low-risk fixes with a confident, auto-safe KB match run unattended."""
    if params.get("require_kb_auto_safe") and not req.get("kb_auto_safe"):
        kb_article = req.get("kb_article_id") or req.get("kb_article") or "on file"
        return "ESCALATE", f"KB article {kb_article} is not marked auto-safe"

    confidence = req.get("confidence")
    if confidence is None:
        return "ESCALATE", "Diagnosis confidence missing; cannot assess risk"

    min_confidence = params.get("min_confidence")
    if min_confidence is None:
        return "ESCALATE", "Minimum confidence threshold is not configured; cannot assess risk"
    if confidence < min_confidence:
        return "ESCALATE", f"Confidence {_round(confidence)} below threshold {_round(min_confidence)}"

    blocked_components = params.get("blocked_components") or []
    component = req.get("component")
    if component is None:
        return "ESCALATE", "Affected component is missing; cannot verify it is safe to auto-remediate"
    if component in blocked_components:
        return "ESCALATE", f"{component} is a protected system"

    if params.get("block_if_reopened") and req.get("is_reopened"):
        return "ESCALATE", "Ticket was previously reopened; automated fix already failed once"

    return "ALLOW", "Diagnosis confidence and KB match meet the bar for automated remediation"


# =============================================================================
# 4. SLA_VIP_ESCALATION
# =============================================================================


def sla_vip_escalation(req: dict, params: dict) -> tuple[str, str]:
    """Escalate tickets close to breaching SLA; VIPs get tighter targets."""
    priority = req.get("priority")
    priority_targets = params.get("priority_targets_hours") or {}
    target_hours: Optional[float] = priority_targets.get(priority) if priority is not None else None

    if req.get("is_vip") and target_hours is not None:
        multiplier = params.get("vip_multiplier")
        if multiplier is not None:
            target_hours = target_hours * multiplier

    remaining_pct = req.get("sla_remaining_pct")
    threshold_pct = params.get("escalate_below_remaining_pct")

    if remaining_pct is None:
        return "ESCALATE", "SLA remaining unknown; cannot assess breach risk"
    if threshold_pct is None:
        return "ESCALATE", "SLA escalation threshold is not configured; cannot assess urgency"

    if remaining_pct < threshold_pct:
        target_desc = f"{_round(target_hours)}h" if target_hours is not None else "an unknown"
        return "ESCALATE", (
            f"SLA remaining is {_round(remaining_pct)}%, below the {_round(threshold_pct)}% escalation threshold "
            f"(priority {priority!r}, target {target_desc})"
        )

    if req.get("sla_status") == "Breached" and params.get("breached_goes_straight_to_lead"):
        return "ESCALATE", "SLA already breached; routing to team lead"

    return "ALLOW", f"SLA on track — {_round(remaining_pct)}% of the target window remaining"


# =============================================================================
# 5. STALL_DETECTION
# =============================================================================


def stall_detection(req: dict, params: dict) -> tuple[str, str]:
    """Flag tickets with no meaningful update beyond the threshold for their priority."""
    priority = req.get("priority")
    stall_thresholds = params.get("stall_hours_by_priority") or {}
    threshold: Optional[float] = stall_thresholds.get(priority) if priority is not None else None

    if threshold is None:
        return "ESCALATE", f"No configured stall threshold for priority {priority!r}; cannot assess staleness"

    if req.get("is_reopened"):
        reduction_pct = params.get("reopened_reduces_threshold_pct")
        if reduction_pct is not None:
            threshold = threshold * (1 - reduction_pct / 100)

    inactive_hours = req.get("inactive_hours")
    if inactive_hours is None:
        return "ESCALATE", "Last update time unknown; cannot assess stall"

    if inactive_hours > threshold:
        return "ESCALATE", (
            f"No update for {_round(inactive_hours)}h, exceeds the {_round(threshold)}h threshold "
            f"for {priority} priority"
        )

    return "ALLOW", f"Ticket active — {_round(inactive_hours)}h inactive is within the {_round(threshold)}h threshold"


# =============================================================================
# Registry
# =============================================================================

RULES: dict[str, RuleFn] = {
    "DATA_COMPLETENESS": data_completeness,
    "CHANGE_APPROVAL_GATE": change_approval_gate,
    "AUTO_REMEDIATION_SAFETY": auto_remediation_safety,
    "SLA_VIP_ESCALATION": sla_vip_escalation,
    "STALL_DETECTION": stall_detection,
}
