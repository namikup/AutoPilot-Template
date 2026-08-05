# tests/test_insight_engine.py
"""
Unit tests for the insight engine (app/services/insight_engine.py).

The generators are SQL aggregations over real tables, so these tests run
against the actual database (see app/core/database.py) rather than mocks.
Each test inserts its own uniquely-tagged rows, asserts only on the insight
matching its own tag, and cleans up afterward — so a test stays correct
no matter what else is sitting in the tables.
"""

import uuid
from datetime import datetime, timedelta

import pytest

from app.core.database import SessionLocal
from app.models.hackathon import Issue, KnowledgeBase
from app.models.policy import Policy, PolicyEvaluation
from app.models.workbench import WorkbenchItem
from app.services.insight_engine import (
    AUTOMATION_CONFIDENCE_FLOOR,
    AUTOMATION_MIN_ESCALATIONS,
    GENERATORS,
    KNOWLEDGE_GAP_MIN_COUNT,
    MAJOR_INCIDENT_MIN_COUNT,
    MAJOR_INCIDENT_WINDOW_MINUTES,
    RECURRING_ERROR_MIN_COUNT,
    SLA_FORECAST_MIN_COUNT,
    _percentile,
    generate_automation_opportunity,
    generate_knowledge_gap,
    generate_major_incident_forming,
    generate_recurring_known_error,
    generate_sla_breach_forecast,
)


def _tag() -> str:
    return uuid.uuid4().hex[:8]


@pytest.fixture
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


def test_registry_contains_all_five_generators():
    assert set(GENERATORS.keys()) == {
        "recurring_known_error",
        "major_incident_forming",
        "sla_breach_forecast",
        "automation_opportunity",
        "knowledge_gap",
    }
    for fn in GENERATORS.values():
        assert callable(fn)


def test_generators_never_raise_and_return_lists(db):
    for generate in GENERATORS.values():
        result = generate(db)
        assert isinstance(result, list)


# ---------------------------------------------------------------------------
# 1. recurring_known_error
# ---------------------------------------------------------------------------


def test_recurring_known_error_emits_create_kb_when_no_kb_matches(db):
    tag = _tag()
    summary = f"Gen test widget jams {tag}"
    component = f"Comp-{tag}"
    issues = [
        Issue(issue_key=f"GT-{tag}-{i}", summary=summary, status="Open", components=component)
        for i in range(RECURRING_ERROR_MIN_COUNT)
    ]
    db.add_all(issues)
    db.commit()
    try:
        results = generate_recurring_known_error(db)
        match = next((r for r in results if r["evidence"].get("component") == component), None)
        assert match is not None
        assert match["evidence"]["count"] == RECURRING_ERROR_MIN_COUNT
        assert match["severity"] == "medium"
        assert match["action_type"] == "create_kb"
        assert len(match["evidence"]["issue_keys"]) == RECURRING_ERROR_MIN_COUNT
    finally:
        for i in issues:
            db.delete(i)
        db.commit()


def test_recurring_known_error_below_threshold_is_not_emitted(db):
    tag = _tag()
    summary = f"Gen test rare glitch {tag}"
    component = f"Comp-{tag}"
    issues = [
        Issue(issue_key=f"GT-{tag}-{i}", summary=summary, status="Open", components=component)
        for i in range(RECURRING_ERROR_MIN_COUNT - 1)
    ]
    db.add_all(issues)
    db.commit()
    try:
        results = generate_recurring_known_error(db)
        match = next((r for r in results if r["evidence"].get("component") == component), None)
        assert match is None
    finally:
        for i in issues:
            db.delete(i)
        db.commit()


def test_recurring_known_error_uses_auto_safe_kb_for_update_policy(db):
    tag = _tag()
    summary = f"Gen test printer jam issue {tag}"
    component = f"Comp-{tag}"
    kb = KnowledgeBase(
        article_id=f"KB-{tag}",
        title=f"Printer jam issue {tag}",
        root_cause="Paper feed misaligned",
        x_auto_safe=True,
    )
    issues = [
        Issue(issue_key=f"GT-{tag}-{i}", summary=summary, status="Open", components=component)
        for i in range(RECURRING_ERROR_MIN_COUNT)
    ]
    db.add(kb)
    db.add_all(issues)
    db.commit()
    try:
        results = generate_recurring_known_error(db)
        match = next((r for r in results if r["evidence"].get("component") == component), None)
        assert match is not None
        assert match["evidence"]["kb_article"] == kb.article_id
        assert match["evidence"]["kb_auto_safe"] is True
        assert match["action_type"] == "update_policy"
        assert match["action_payload"]["policy_id"] == "AUTO_REMEDIATION_SAFETY"
        # The new blocked_components list is directly mergeable — it must
        # never contain the component this insight is unblocking.
        assert component not in match["action_payload"]["params"]["blocked_components"]
    finally:
        for i in issues:
            db.delete(i)
        db.delete(kb)
        db.commit()


# ---------------------------------------------------------------------------
# 2. major_incident_forming
# ---------------------------------------------------------------------------


def test_major_incident_forming_clusters_burst_within_window(db):
    tag = _tag()
    component = f"Comp-{tag}"
    base = datetime(2026, 1, 1, 12, 0, 0)
    issues = [
        Issue(
            issue_key=f"GT-{tag}-{i}",
            summary=f"Gen test outage {tag}",
            status="Open",
            components=component,
            created=(base + timedelta(minutes=i * 5)).strftime("%Y-%m-%d %H:%M:%S"),
            reporter=f"user{i % 3}@example.com",
        )
        for i in range(MAJOR_INCIDENT_MIN_COUNT)
    ]
    db.add_all(issues)
    db.commit()
    try:
        results = generate_major_incident_forming(db)
        match = next((r for r in results if r["evidence"].get("component") == component), None)
        assert match is not None
        assert match["evidence"]["count"] == MAJOR_INCIDENT_MIN_COUNT
        assert match["severity"] == "critical"
        assert match["evidence"]["distinct_reporters"] == 3
        assert match["action_type"] == "open_incident"
    finally:
        for i in issues:
            db.delete(i)
        db.commit()


def test_major_incident_forming_spread_out_does_not_cluster(db):
    tag = _tag()
    component = f"Comp-{tag}"
    base = datetime(2026, 1, 1, 12, 0, 0)
    gap = timedelta(minutes=MAJOR_INCIDENT_WINDOW_MINUTES + 5)
    issues = [
        Issue(
            issue_key=f"GT-{tag}-{i}",
            summary=f"Gen test slow trickle {tag}",
            status="Open",
            components=component,
            created=(base + gap * i).strftime("%Y-%m-%d %H:%M:%S"),
        )
        for i in range(MAJOR_INCIDENT_MIN_COUNT)
    ]
    db.add_all(issues)
    db.commit()
    try:
        results = generate_major_incident_forming(db)
        match = next((r for r in results if r["evidence"].get("component") == component), None)
        assert match is None
    finally:
        for i in issues:
            db.delete(i)
        db.commit()


# ---------------------------------------------------------------------------
# 3. sla_breach_forecast
# ---------------------------------------------------------------------------


def test_sla_breach_forecast_emits_for_at_risk_group(db):
    tag = _tag()
    group = f"GenTestTeam-{tag}"
    at_risk = [
        Issue(
            issue_key=f"GT-{tag}-{i}",
            summary=f"Gen test sla issue {tag}",
            status="Open",
            assignment_group=group,
            priority="Highest" if i == 0 else "Medium",
            time_to_resolution="At risk",
        )
        for i in range(SLA_FORECAST_MIN_COUNT)
    ]
    breached = Issue(
        issue_key=f"GT-{tag}-breached",
        summary=f"Gen test sla issue {tag}",
        status="Open",
        assignment_group=group,
        priority="High",
        time_to_resolution="Breached",
    )
    db.add_all(at_risk + [breached])
    db.commit()
    try:
        results = generate_sla_breach_forecast(db)
        match = next((r for r in results if r["evidence"].get("assignment_group") == group), None)
        assert match is not None
        assert match["evidence"]["at_risk_count"] == SLA_FORECAST_MIN_COUNT
        assert match["evidence"]["already_breached_count"] == 1
        assert match["evidence"]["priority_breakdown"].get("Highest") == 1
        assert match["severity"] == "critical"
        assert match["action_type"] == "reassign"
    finally:
        for i in at_risk + [breached]:
            db.delete(i)
        db.commit()


def test_sla_breach_forecast_high_severity_without_highest_priority(db):
    tag = _tag()
    group = f"GenTestTeam-{tag}"
    at_risk = [
        Issue(
            issue_key=f"GT-{tag}-{i}",
            summary=f"Gen test sla issue {tag}",
            status="Open",
            assignment_group=group,
            priority="Medium",
            time_to_resolution="At risk",
        )
        for i in range(SLA_FORECAST_MIN_COUNT)
    ]
    db.add_all(at_risk)
    db.commit()
    try:
        results = generate_sla_breach_forecast(db)
        match = next((r for r in results if r["evidence"].get("assignment_group") == group), None)
        assert match is not None
        assert match["severity"] == "high"
        assert match["evidence"]["already_breached_count"] == 0
    finally:
        for i in at_risk:
            db.delete(i)
        db.commit()


# ---------------------------------------------------------------------------
# 4. automation_opportunity
# ---------------------------------------------------------------------------


def test_automation_opportunity_detects_over_escalating_policy(db):
    tag = _tag()
    policy_id = f"GENTEST_POLICY_{tag}"
    policy = Policy(
        id=policy_id,
        name="Gen Test Policy",
        category="test",
        enabled=True,
        priority=999,
        params={"min_confidence": 0.9},
        version=1,
        updated_by="test",
    )
    db.add(policy)
    db.commit()

    n = AUTOMATION_MIN_ESCALATIONS
    approved_n = int(n * 0.9)  # 90% approval — above the 80% threshold
    approved_confidences = [0.60 + 0.03 * i for i in range(approved_n)]

    evaluations = []
    workbench_items = []
    for i in range(n):
        issue_key = f"GT-{tag}-{i}"
        is_approved = i < approved_n
        confidence = approved_confidences[i] if is_approved else 0.95
        evaluations.append(
            PolicyEvaluation(
                id=str(uuid.uuid4()),
                run_id=f"gentest-{tag}",
                issue_key=issue_key,
                policy_id=policy_id,
                policy_version=1,
                verdict="ESCALATE",
                reason=f"Confidence {confidence} below threshold",
                input_snapshot={"confidence": confidence},
                params_used=policy.params,
            )
        )
        workbench_items.append(
            WorkbenchItem(
                ticket_key=issue_key,
                summary="Gen test ticket",
                status="approved" if is_approved else "rejected",
            )
        )

    db.add_all(evaluations)
    db.add_all(workbench_items)
    db.commit()
    try:
        results = generate_automation_opportunity(db)
        match = next((r for r in results if r["evidence"].get("policy_id") == policy_id), None)
        assert match is not None
        assert match["evidence"]["escalation_count"] == n
        assert match["evidence"]["approved_count"] == approved_n
        assert match["evidence"]["approval_rate"] == pytest.approx(approved_n / n, abs=1e-4)
        assert match["severity"] == "high"
        assert match["action_type"] == "update_policy"

        expected_suggestion = max(AUTOMATION_CONFIDENCE_FLOOR, round(_percentile(approved_confidences, 10), 2))
        assert match["action_payload"]["params"]["min_confidence"] == expected_suggestion
    finally:
        # Two-phase delete: Policy <-> PolicyEvaluation has no ORM
        # relationship(), so SQLAlchemy won't auto-order deletes across
        # that FK — the child rows must be committed before the parent.
        for wi in workbench_items:
            db.delete(wi)
        for pe in evaluations:
            db.delete(pe)
        db.commit()
        db.delete(policy)
        db.commit()


def test_automation_opportunity_ignores_policy_below_approval_threshold(db):
    tag = _tag()
    policy_id = f"GENTEST_POLICY_{tag}"
    policy = Policy(
        id=policy_id,
        name="Gen Test Policy",
        category="test",
        enabled=True,
        priority=999,
        params={"min_confidence": 0.9},
        version=1,
        updated_by="test",
    )
    db.add(policy)
    db.commit()

    n = AUTOMATION_MIN_ESCALATIONS
    approved_n = int(n * 0.5)  # only 50% approved — below the 80% threshold

    evaluations = []
    workbench_items = []
    for i in range(n):
        issue_key = f"GT-{tag}-{i}"
        is_approved = i < approved_n
        evaluations.append(
            PolicyEvaluation(
                id=str(uuid.uuid4()),
                run_id=f"gentest-{tag}",
                issue_key=issue_key,
                policy_id=policy_id,
                policy_version=1,
                verdict="ESCALATE",
                reason="test",
                input_snapshot={"confidence": 0.7},
            )
        )
        workbench_items.append(
            WorkbenchItem(
                ticket_key=issue_key,
                summary="Gen test ticket",
                status="approved" if is_approved else "rejected",
            )
        )

    db.add_all(evaluations)
    db.add_all(workbench_items)
    db.commit()
    try:
        results = generate_automation_opportunity(db)
        match = next((r for r in results if r["evidence"].get("policy_id") == policy_id), None)
        assert match is None
    finally:
        # Two-phase delete: Policy <-> PolicyEvaluation has no ORM
        # relationship(), so SQLAlchemy won't auto-order deletes across
        # that FK — the child rows must be committed before the parent.
        for wi in workbench_items:
            db.delete(wi)
        for pe in evaluations:
            db.delete(pe)
        db.commit()
        db.delete(policy)
        db.commit()


# ---------------------------------------------------------------------------
# 5. knowledge_gap
# ---------------------------------------------------------------------------


def test_knowledge_gap_emits_when_no_kb_matches(db):
    tag = _tag()
    summary = f"Gen test mystery fault {tag}"
    issues = [
        Issue(issue_key=f"GT-{tag}-{i}", summary=summary, status="Open", components=f"Comp-{tag}")
        for i in range(KNOWLEDGE_GAP_MIN_COUNT)
    ]
    db.add_all(issues)
    db.commit()
    try:
        results = generate_knowledge_gap(db)
        match = next((r for r in results if r["evidence"].get("summary") == summary), None)
        assert match is not None
        assert match["evidence"]["count"] == KNOWLEDGE_GAP_MIN_COUNT
        assert match["action_type"] == "create_kb"
    finally:
        for i in issues:
            db.delete(i)
        db.commit()


def test_knowledge_gap_suppressed_when_kb_matches(db):
    tag = _tag()
    summary = f"Gen test known fault pattern {tag}"
    kb = KnowledgeBase(
        article_id=f"KB-{tag}",
        title=f"Known fault pattern {tag}",
        root_cause="documented",
        x_auto_safe=False,
    )
    issues = [
        Issue(issue_key=f"GT-{tag}-{i}", summary=summary, status="Open", components=f"Comp-{tag}")
        for i in range(KNOWLEDGE_GAP_MIN_COUNT)
    ]
    db.add(kb)
    db.add_all(issues)
    db.commit()
    try:
        results = generate_knowledge_gap(db)
        match = next((r for r in results if r["evidence"].get("summary") == summary), None)
        assert match is None
    finally:
        for i in issues:
            db.delete(i)
        db.delete(kb)
        db.commit()
