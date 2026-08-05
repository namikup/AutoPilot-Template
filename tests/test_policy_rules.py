# tests/test_policy_rules.py
"""
Unit tests for the policy rules engine (app/services/policy_rules.py).

Each rule is tested for its ALLOW branch, each of its ESCALATE branches,
and a "never crashes on missing data" case using an empty request payload.
"""

from app.services.policy_rules import (
    RULES,
    auto_remediation_safety,
    change_approval_gate,
    data_completeness,
    sla_vip_escalation,
    stall_detection,
)

# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


def test_registry_contains_all_five_policies():
    assert set(RULES.keys()) == {
        "DATA_COMPLETENESS",
        "CHANGE_APPROVAL_GATE",
        "AUTO_REMEDIATION_SAFETY",
        "SLA_VIP_ESCALATION",
        "STALL_DETECTION",
    }
    for fn in RULES.values():
        assert callable(fn)


# ---------------------------------------------------------------------------
# 1. DATA_COMPLETENESS
# ---------------------------------------------------------------------------

DATA_COMPLETENESS_PARAMS = {
    "required_fields": ["x_channel", "x_confidence", "Components", "Reporter"],
    "on_missing": "ESCALATE",
    "allow_inference": False,
}


def test_data_completeness_allows_when_all_fields_present():
    req = {"x_channel": "email", "x_confidence": 0.9, "Components": "Billing", "Reporter": "a@b.com"}
    verdict, reason = data_completeness(req, DATA_COMPLETENESS_PARAMS)
    assert verdict == "ALLOW"
    assert "present" in reason.lower()


def test_data_completeness_escalates_on_missing_field():
    req = {"x_channel": "email", "x_confidence": 0.9, "Components": "Billing"}  # Reporter missing
    verdict, reason = data_completeness(req, DATA_COMPLETENESS_PARAMS)
    assert verdict == "ESCALATE"
    assert "Reporter" in reason


def test_data_completeness_treats_blank_string_as_missing():
    req = {"x_channel": "   ", "x_confidence": 0.9, "Components": "Billing", "Reporter": "a@b.com"}
    verdict, reason = data_completeness(req, DATA_COMPLETENESS_PARAMS)
    assert verdict == "ESCALATE"
    assert "x_channel" in reason


def test_data_completeness_uses_configured_on_missing_verdict():
    params = {**DATA_COMPLETENESS_PARAMS, "on_missing": "DENY"}
    verdict, _ = data_completeness({}, params)
    assert verdict == "DENY"


def test_data_completeness_never_crashes_on_empty_input():
    verdict, reason = data_completeness({}, DATA_COMPLETENESS_PARAMS)
    assert verdict == "ESCALATE"
    assert isinstance(reason, str)


# ---------------------------------------------------------------------------
# 2. CHANGE_APPROVAL_GATE
# ---------------------------------------------------------------------------

CHANGE_APPROVAL_PARAMS = {
    "block_risk_levels": ["High"],
    "require_cab_when_flagged": True,
    "auto_approve_low_risk": False,
    "rollback_requires_approval": True,
}


def test_change_approval_gate_allows_low_risk_change():
    req = {"change_required": True, "risk": "Low"}
    verdict, _ = change_approval_gate(req, CHANGE_APPROVAL_PARAMS)
    assert verdict == "ALLOW"


def test_change_approval_gate_escalates_high_risk_change():
    req = {"change_required": True, "risk": "High", "change_id": "CHG-1029"}
    verdict, reason = change_approval_gate(req, CHANGE_APPROVAL_PARAMS)
    assert verdict == "ESCALATE"
    assert "CHG-1029" in reason
    assert "High" in reason


def test_change_approval_gate_escalates_when_cab_flagged():
    req = {"cab_approval_required": True}
    verdict, reason = change_approval_gate(req, CHANGE_APPROVAL_PARAMS)
    assert verdict == "ESCALATE"
    assert "CAB" in reason


def test_change_approval_gate_escalates_rollback():
    req = {"is_rollback": True}
    verdict, reason = change_approval_gate(req, CHANGE_APPROVAL_PARAMS)
    assert verdict == "ESCALATE"
    assert "Rollback" in reason


def test_change_approval_gate_escalates_when_risk_missing_for_required_change():
    req = {"change_required": True}
    verdict, reason = change_approval_gate(req, CHANGE_APPROVAL_PARAMS)
    assert verdict == "ESCALATE"
    assert "risk" in reason.lower()


def test_change_approval_gate_never_crashes_on_empty_input():
    verdict, reason = change_approval_gate({}, CHANGE_APPROVAL_PARAMS)
    assert verdict == "ALLOW"
    assert isinstance(reason, str)


# ---------------------------------------------------------------------------
# 3. AUTO_REMEDIATION_SAFETY
# ---------------------------------------------------------------------------

AUTO_REMEDIATION_PARAMS = {
    "min_confidence": 0.80,
    "require_kb_auto_safe": True,
    "blocked_components": ["Payroll", "SSO"],
    "max_priority_for_auto": "High",
    "block_if_reopened": True,
}


def _valid_remediation_req(**overrides):
    req = {
        "kb_auto_safe": True,
        "kb_article_id": "KB-103",
        "confidence": 0.95,
        "component": "Email",
        "is_reopened": False,
    }
    req.update(overrides)
    return req


def test_auto_remediation_allows_safe_high_confidence_fix():
    verdict, _ = auto_remediation_safety(_valid_remediation_req(), AUTO_REMEDIATION_PARAMS)
    assert verdict == "ALLOW"


def test_auto_remediation_escalates_when_kb_not_auto_safe():
    req = _valid_remediation_req(kb_auto_safe=False)
    verdict, reason = auto_remediation_safety(req, AUTO_REMEDIATION_PARAMS)
    assert verdict == "ESCALATE"
    assert "KB-103" in reason


def test_auto_remediation_escalates_on_missing_confidence():
    req = _valid_remediation_req(confidence=None)
    verdict, reason = auto_remediation_safety(req, AUTO_REMEDIATION_PARAMS)
    assert verdict == "ESCALATE"
    assert "confidence" in reason.lower()


def test_auto_remediation_escalates_below_confidence_threshold():
    req = _valid_remediation_req(confidence=0.5)
    verdict, reason = auto_remediation_safety(req, AUTO_REMEDIATION_PARAMS)
    assert verdict == "ESCALATE"
    assert "0.5" in reason
    assert "0.8" in reason


def test_auto_remediation_escalates_on_protected_component():
    req = _valid_remediation_req(component="Payroll")
    verdict, reason = auto_remediation_safety(req, AUTO_REMEDIATION_PARAMS)
    assert verdict == "ESCALATE"
    assert "Payroll" in reason


def test_auto_remediation_escalates_on_reopened_ticket():
    req = _valid_remediation_req(is_reopened=True)
    verdict, reason = auto_remediation_safety(req, AUTO_REMEDIATION_PARAMS)
    assert verdict == "ESCALATE"
    assert "reopened" in reason.lower()


def test_auto_remediation_never_crashes_on_empty_input():
    verdict, reason = auto_remediation_safety({}, AUTO_REMEDIATION_PARAMS)
    assert verdict == "ESCALATE"
    assert isinstance(reason, str)


# ---------------------------------------------------------------------------
# 4. SLA_VIP_ESCALATION
# ---------------------------------------------------------------------------

SLA_PARAMS = {
    "escalate_below_remaining_pct": 25,
    "priority_targets_hours": {"Highest": 4, "High": 8, "Medium": 24, "Low": 48},
    "vip_multiplier": 2.0,
    "vip_ignores_business_hours": True,
    "breached_goes_straight_to_lead": True,
}


def test_sla_allows_when_plenty_of_time_remaining():
    req = {"priority": "Medium", "sla_remaining_pct": 80, "sla_status": "On Track"}
    verdict, _ = sla_vip_escalation(req, SLA_PARAMS)
    assert verdict == "ALLOW"


def test_sla_escalates_below_remaining_threshold():
    req = {"priority": "Medium", "sla_remaining_pct": 10, "sla_status": "At Risk"}
    verdict, reason = sla_vip_escalation(req, SLA_PARAMS)
    assert verdict == "ESCALATE"
    assert "10" in reason
    assert "25" in reason


def test_sla_escalates_when_already_breached():
    req = {"priority": "Low", "sla_remaining_pct": 60, "sla_status": "Breached"}
    verdict, reason = sla_vip_escalation(req, SLA_PARAMS)
    assert verdict == "ESCALATE"
    assert "breached" in reason.lower()


def test_sla_vip_ticket_uses_multiplier_in_reason():
    # target for High = 8h; VIP multiplier 2.0 -> 16h shown in the reason.
    req = {"priority": "High", "sla_remaining_pct": 5, "is_vip": True}
    verdict, reason = sla_vip_escalation(req, SLA_PARAMS)
    assert verdict == "ESCALATE"
    assert "16" in reason


def test_sla_escalates_on_missing_remaining_pct():
    req = {"priority": "Medium"}
    verdict, reason = sla_vip_escalation(req, SLA_PARAMS)
    assert verdict == "ESCALATE"
    assert "remaining" in reason.lower()


def test_sla_never_crashes_on_empty_input():
    verdict, reason = sla_vip_escalation({}, SLA_PARAMS)
    assert verdict == "ESCALATE"
    assert isinstance(reason, str)


# ---------------------------------------------------------------------------
# 5. STALL_DETECTION
# ---------------------------------------------------------------------------

STALL_PARAMS = {
    "stall_hours_by_priority": {"Highest": 4, "High": 12, "Medium": 24, "Low": 48},
    "count_business_hours_only": True,
    "waiting_for_customer_pauses_clock": True,
    "reopened_reduces_threshold_pct": 50,
}


def test_stall_allows_recent_update():
    req = {"priority": "Medium", "inactive_hours": 5, "is_reopened": False}
    verdict, _ = stall_detection(req, STALL_PARAMS)
    assert verdict == "ALLOW"


def test_stall_escalates_when_exceeding_threshold():
    req = {"priority": "Medium", "inactive_hours": 30, "is_reopened": False}
    verdict, reason = stall_detection(req, STALL_PARAMS)
    assert verdict == "ESCALATE"
    assert "30" in reason
    assert "24" in reason


def test_stall_reopened_ticket_uses_tighter_threshold():
    # Medium threshold is 24h; reopened reduces it by 50% -> 12h.
    # 15h inactive would ALLOW at the normal threshold but ESCALATE once reopened.
    req = {"priority": "Medium", "inactive_hours": 15, "is_reopened": True}
    verdict, reason = stall_detection(req, STALL_PARAMS)
    assert verdict == "ESCALATE"
    assert "12" in reason


def test_stall_escalates_on_unknown_priority():
    req = {"priority": "Unknown", "inactive_hours": 1}
    verdict, reason = stall_detection(req, STALL_PARAMS)
    assert verdict == "ESCALATE"
    assert "threshold" in reason.lower()


def test_stall_never_crashes_on_empty_input():
    verdict, reason = stall_detection({}, STALL_PARAMS)
    assert verdict == "ESCALATE"
    assert isinstance(reason, str)
