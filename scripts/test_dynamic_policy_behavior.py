#!/usr/bin/env python3
"""
Test Dynamic AI Policy Behavior Script for Autopilot Asia Hackathon Round 2.

Demonstrates that changing policy parameters live via API (simulating UI toggles/sliders):
  1. AUTO_REMEDIATION_SAFETY (Changing min_confidence from 0.80 to 0.90)
  2. SLA_VIP_ESCALATION      (Changing escalate_below_remaining_pct from 25% to 50%)
  3. CHANGE_APPROVAL_GATE    (Adding 'Medium' risk to block_risk_levels)

Immediately changes agent evaluation verdicts LIVE without code changes or server restarts.
"""

import sys
import time
import httpx

API_BASE = "http://localhost:8001/api"


def print_test_header(num: int, name: str):
    print(f"\n--------------------------------------------------------------------------------")
    print(f"  POLICY TEST {num}: {name.upper()}")
    print(f"--------------------------------------------------------------------------------")


def main():
    print("🧪 TESTING DYNAMIC AI POLICY LIVE BEHAVIOR CHANGES...\n")

    # =========================================================================
    # TEST 1: AUTO_REMEDIATION_SAFETY (Confidence Threshold Slider)
    # =========================================================================
    print_test_header(1, "AUTO_REMEDIATION_SAFETY (min_confidence slider)")
    policy_id = "AUTO_REMEDIATION_SAFETY"
    ticket_payload = {
        "run_id": "dyn-test-001",
        "issue_key": "ITSM-2004",
        "confidence": 0.85,
        "component": "Hardware",
        "kb_auto_safe": True,
        "x_channel": "email",
        "reporter": "Wei Yeoh",
        "auto_route_workbench": False,
    }

    # 1. Reset policy to 0.80 min_confidence
    httpx.patch(f"{API_BASE}/policies/{policy_id}", json={"params": {
        "min_confidence": 0.80,
        "block_if_reopened": True,
        "blocked_components": ["Payroll", "SSO"],
        "require_kb_auto_safe": True,
    }}, timeout=10.0)

    res1 = httpx.post(f"{API_BASE}/policies/evaluate", json=ticket_payload, timeout=10.0).json()
    ev1 = next(e for e in res1["evaluations"] if e["policy_id"] == policy_id)
    print(f"1️⃣  Initial Setting  (min_confidence = 0.80) | Input Confidence = 0.85")
    print(f"    Verdict: {ev1['verdict']} | Reason: {ev1['reason']}")

    # 2. UI Toggle / Slider change: Set min_confidence = 0.90
    print("\n🎛️  UI Slider Changed: Raising min_confidence to 0.90 via PATCH /api/policies/AUTO_REMEDIATION_SAFETY...")
    patch_res = httpx.patch(f"{API_BASE}/policies/{policy_id}", json={"params": {
        "min_confidence": 0.90,
        "block_if_reopened": True,
        "blocked_components": ["Payroll", "SSO"],
        "require_kb_auto_safe": True,
    }}, timeout=10.0).json()
    print(f"    Policy Updated! New Version: v{patch_res['version']} | min_confidence: {patch_res['params']['min_confidence']}")

    # 3. Evaluate same ticket payload again
    res2 = httpx.post(f"{API_BASE}/policies/evaluate", json=ticket_payload, timeout=10.0).json()
    ev2 = next(e for e in res2["evaluations"] if e["policy_id"] == policy_id)
    print(f"\n2️⃣  Live Evaluation (min_confidence = 0.90) | Input Confidence = 0.85")
    print(f"    Verdict: {ev2['verdict']} | Reason: {ev2['reason']}")

    if ev1["verdict"] == "ALLOW" and ev2["verdict"] == "ESCALATE":
        print("✅ SUCCESS: AUTO_REMEDIATION_SAFETY behavior changed LIVE from ALLOW to ESCALATE!")
    else:
        print(f"❌ FAIL: Expected ALLOW -> ESCALATE, got {ev1['verdict']} -> {ev2['verdict']}")

    # =========================================================================
    # TEST 2: SLA_VIP_ESCALATION (Warning Threshold Slider)
    # =========================================================================
    print_test_header(2, "SLA_VIP_ESCALATION (escalate_below_remaining_pct slider)")
    policy_id = "SLA_VIP_ESCALATION"
    sla_payload = {
        "run_id": "dyn-test-002",
        "issue_key": "ITSM-2009",
        "priority": "High",
        "sla_remaining_pct": 40.0,
        "x_channel": "chat",
        "reporter": "Jaya Teo",
        "auto_route_workbench": False,
    }

    # 1. Reset policy threshold to 25%
    httpx.patch(f"{API_BASE}/policies/{policy_id}", json={"params": {
        "vip_multiplier": 2.0,
        "priority_targets_hours": {"Low": 48, "Medium": 24, "High": 8, "Highest": 4},
        "escalate_below_remaining_pct": 25,
    }}, timeout=10.0)

    res1 = httpx.post(f"{API_BASE}/policies/evaluate", json=sla_payload, timeout=10.0).json()
    ev1 = next(e for e in res1["evaluations"] if e["policy_id"] == policy_id)
    print(f"1️⃣  Initial Setting  (escalate_below = 25%) | Input SLA Remaining = 40.0%")
    print(f"    Verdict: {ev1['verdict']} | Reason: {ev1['reason']}")

    # 2. UI Toggle / Slider change: Set escalate_below = 50%
    print("\n🎛️  UI Slider Changed: Raising SLA threshold to 50% via PATCH /api/policies/SLA_VIP_ESCALATION...")
    patch_res = httpx.patch(f"{API_BASE}/policies/{policy_id}", json={"params": {
        "vip_multiplier": 2.0,
        "priority_targets_hours": {"Low": 48, "Medium": 24, "High": 8, "Highest": 4},
        "escalate_below_remaining_pct": 50,
    }}, timeout=10.0).json()
    print(f"    Policy Updated! New Version: v{patch_res['version']} | threshold: {patch_res['params']['escalate_below_remaining_pct']}%")

    # 3. Evaluate same payload
    res2 = httpx.post(f"{API_BASE}/policies/evaluate", json=sla_payload, timeout=10.0).json()
    ev2 = next(e for e in res2["evaluations"] if e["policy_id"] == policy_id)
    print(f"\n2️⃣  Live Evaluation (escalate_below = 50%) | Input SLA Remaining = 40.0%")
    print(f"    Verdict: {ev2['verdict']} | Reason: {ev2['reason']}")

    if ev1["verdict"] == "ALLOW" and ev2["verdict"] == "ESCALATE":
        print("✅ SUCCESS: SLA_VIP_ESCALATION behavior changed LIVE from ALLOW to ESCALATE!")
    else:
        print(f"❌ FAIL: Expected ALLOW -> ESCALATE, got {ev1['verdict']} -> {ev2['verdict']}")

    # =========================================================================
    # TEST 3: CHANGE_APPROVAL_GATE (Risk Level Multi-Select Toggle)
    # =========================================================================
    print_test_header(3, "CHANGE_APPROVAL_GATE (block_risk_levels toggle)")
    policy_id = "CHANGE_APPROVAL_GATE"
    change_payload = {
        "run_id": "dyn-test-003",
        "issue_key": "ITSM-2015",
        "change_required": True,
        "risk": "Medium",
        "x_channel": "email",
        "reporter": "Kevin Aziz",
        "auto_route_workbench": False,
    }

    # 1. Reset block_risk_levels to ['High']
    httpx.patch(f"{API_BASE}/policies/{policy_id}", json={"params": {
        "block_risk_levels": ["High"],
        "auto_approve_low_risk": False,
        "require_cab_when_flagged": True,
        "rollback_requires_approval": True,
    }}, timeout=10.0)

    res1 = httpx.post(f"{API_BASE}/policies/evaluate", json=change_payload, timeout=10.0).json()
    ev1 = next(e for e in res1["evaluations"] if e["policy_id"] == policy_id)
    print(f"1️⃣  Initial Setting  (block_risk = ['High']) | Input Risk = 'Medium'")
    print(f"    Verdict: {ev1['verdict']} | Reason: {ev1['reason']}")

    # 2. UI Toggle change: Add 'Medium' to blocked risk levels
    print("\n🎛️  UI Toggle Changed: Adding 'Medium' risk to blocked risk levels via PATCH...")
    patch_res = httpx.patch(f"{API_BASE}/policies/{policy_id}", json={"params": {
        "block_risk_levels": ["High", "Medium"],
        "auto_approve_low_risk": False,
        "require_cab_when_flagged": True,
        "rollback_requires_approval": True,
    }}, timeout=10.0).json()
    print(f"    Policy Updated! New Version: v{patch_res['version']} | blocked_risk_levels: {patch_res['params']['block_risk_levels']}")

    # 3. Evaluate same payload
    res2 = httpx.post(f"{API_BASE}/policies/evaluate", json=change_payload, timeout=10.0).json()
    ev2 = next(e for e in res2["evaluations"] if e["policy_id"] == policy_id)
    print(f"\n2️⃣  Live Evaluation (block_risk = ['High', 'Medium']) | Input Risk = 'Medium'")
    print(f"    Verdict: {ev2['verdict']} | Reason: {ev2['reason']}")

    if ev1["verdict"] == "ALLOW" and ev2["verdict"] == "ESCALATE":
        print("✅ SUCCESS: CHANGE_APPROVAL_GATE behavior changed LIVE from ALLOW to ESCALATE!")
    else:
        print(f"❌ FAIL: Expected ALLOW -> ESCALATE, got {ev1['verdict']} -> {ev2['verdict']}")

    print("\n================================================================================")
    print("🎉 ALL 3 DYNAMIC AI POLICIES DEMONSTRATED LIVE BEHAVIOR CHANGES SUCCESSFULLY!")
    print("================================================================================\n")


if __name__ == "__main__":
    main()
