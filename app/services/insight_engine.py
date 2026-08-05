# app/services/insight_engine.py
"""
Insight Engine — pure(ish) computation functions that scan operational data
(issues, policy evaluations, workbench decisions) and surface AI Insights.

Each generator takes a database session and returns zero or more insight
dicts, ready to be unpacked into an Insight(**d) row:

    from app.services.insight_engine import GENERATORS

    for insight_type, generate in GENERATORS.items():
        for insight_dict in generate(db):
            db.add(Insight(**insight_dict))

Design principle — data-driven, never hardcoded:
    Every ticket key, summary, KB id, count, and suggested threshold in the
    returned dicts is computed from what's actually in the database at call
    time. Nothing here should need to change to run against a different
    dataset. The only things that ARE hardcoded are the tunable thresholds
    below (group sizes, time windows, percentiles) and a handful of known
    status/priority label strings the generators filter on — both are
    business-logic constants, not data.

Design principle — never raise, never assume:
    A generator with no qualifying data returns an empty list. Malformed
    or unparseable rows (e.g. a `created` timestamp in an unexpected
    format) are skipped, not fatal.
"""

import math
import re
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from typing import Callable, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from ..models.hackathon import Issue, KnowledgeBase
from ..models.policy import Policy, PolicyEvaluation
from ..models.workbench import WorkbenchItem

GeneratorFn = Callable[[Session], list[dict]]

# =============================================================================
# Tunable thresholds — every magic number a generator uses lives here.
# =============================================================================

# 1. recurring_known_error
RECURRING_ERROR_MIN_COUNT = 5
RECURRING_ERROR_HIGH_COUNT = 10
RECURRING_ERROR_CRITICAL_COUNT = 15
RECURRING_ERROR_SAMPLE_SIZE = 10

# 2. major_incident_forming
MAJOR_INCIDENT_MIN_COUNT = 8
MAJOR_INCIDENT_WINDOW_MINUTES = 60

# 3. sla_breach_forecast
SLA_FORECAST_MIN_COUNT = 5

# 4. automation_opportunity
AUTOMATION_MIN_ESCALATIONS = 10
AUTOMATION_APPROVAL_RATE_THRESHOLD = 0.80
AUTOMATION_CONFIDENCE_PERCENTILE = 10  # use the 10th percentile of approved confidences
AUTOMATION_CONFIDENCE_FLOOR = 0.50  # never suggest going below this, however low the data points
AUTOMATION_SAMPLE_REASON_SIZE = 5

# 5. knowledge_gap
KNOWLEDGE_GAP_MIN_COUNT = 4

# Shared: fuzzy KB title/root_cause matching (word-overlap ratio, 0..1)
KB_MATCH_MIN_OVERLAP = 0.5

# Known label strings the generators filter on (business constants, not data)
STATUS_RESOLVED = "Resolved"
SLA_AT_RISK = "At risk"
SLA_BREACHED = "Breached"
PRIORITY_HIGHEST = "Highest"
WORKBENCH_APPROVED = "approved"

# Policy this insight type is qualified to propose a numeric tweak for.
AUTO_REMEDIATION_POLICY_ID = "AUTO_REMEDIATION_SAFETY"

_STOPWORDS = {
    "a", "an", "the", "for", "on", "in", "of", "to", "and", "is", "are",
    "after", "with", "when", "issue", "error",
}

_DATE_FORMATS = (
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d",
    "%b %d %Y",
    "%d/%m/%Y",
)


# =============================================================================
# Shared helpers
# =============================================================================


def _parse_created(raw: Optional[str]) -> Optional[datetime]:
    """Parse Issue.created (stored as a raw, inconsistently-formatted string)."""
    if not raw:
        return None
    raw = raw.strip()
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            continue
    return None


def _normalize_words(text: str) -> set[str]:
    words = set(re.findall(r"[a-z0-9]+", (text or "").lower()))
    return words - _STOPWORDS


def _word_overlap_score(a: str, b: str) -> float:
    words_a, words_b = _normalize_words(a), _normalize_words(b)
    if not words_a or not words_b:
        return 0.0
    return len(words_a & words_b) / min(len(words_a), len(words_b))


def _find_matching_kb(kb_articles: list[KnowledgeBase], text: str) -> Optional[KnowledgeBase]:
    """Best fuzzy match for `text` against KB titles/root causes, or None."""
    best, best_score = None, 0.0
    for kb in kb_articles:
        score = max(
            _word_overlap_score(text, kb.title or ""),
            _word_overlap_score(text, kb.root_cause or ""),
        )
        if score > best_score:
            best, best_score = kb, score
    return best if best_score >= KB_MATCH_MIN_OVERLAP else None


def _percentile(values: list[float], pct: float) -> float:
    """Linear-interpolation percentile (numpy's default 'linear' method)."""
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    k = (pct / 100) * (len(ordered) - 1)
    lo, hi = math.floor(k), math.ceil(k)
    if lo == hi:
        return ordered[int(k)]
    return ordered[lo] * (hi - k) + ordered[hi] * (k - lo)


def _cluster_by_time_window(
    points: list[tuple[datetime, str, Optional[str]]],
    window: timedelta,
    min_count: int,
) -> list[list[tuple[datetime, str, Optional[str]]]]:
    """
    Given (timestamp, issue_key, reporter) points, find bursts where some
    rolling window of size `window` contains at least `min_count` points.
    Overlapping qualifying windows are merged into a single cluster.
    """
    ordered = sorted(points, key=lambda p: p[0])
    n = len(ordered)
    qualifies = [False] * n

    left = 0
    for right in range(n):
        while ordered[right][0] - ordered[left][0] > window:
            left += 1
        if right - left + 1 >= min_count:
            for i in range(left, right + 1):
                qualifies[i] = True

    clusters: list[list[tuple[datetime, str, Optional[str]]]] = []
    current: list[tuple[datetime, str, Optional[str]]] = []
    for i in range(n):
        if qualifies[i]:
            current.append(ordered[i])
        else:
            if current:
                clusters.append(current)
                current = []
    if current:
        clusters.append(current)
    return clusters


def _severity_by_count(count: int, critical_at: int, high_at: int) -> str:
    if count >= critical_at:
        return "critical"
    if count >= high_at:
        return "high"
    return "medium"


# =============================================================================
# 1. recurring_known_error
# =============================================================================


def generate_recurring_known_error(db: Session) -> list[dict]:
    """Repeated open tickets sharing the same summary + component."""
    groups = (
        db.query(Issue.summary, Issue.components, func.count(Issue.id).label("cnt"))
        .filter(Issue.status != STATUS_RESOLVED)
        .filter(Issue.summary.isnot(None))
        .filter(Issue.components.isnot(None))
        .group_by(Issue.summary, Issue.components)
        .having(func.count(Issue.id) >= RECURRING_ERROR_MIN_COUNT)
        .all()
    )
    if not groups:
        return []

    kb_articles = db.query(KnowledgeBase).all()
    total_issues = db.query(func.count(Issue.id)).scalar() or 0
    auto_remediation_policy = (
        db.query(Policy).filter(Policy.id == AUTO_REMEDIATION_POLICY_ID).first()
    )

    insights: list[dict] = []
    for summary, component, count in groups:
        issue_keys = [
            row[0]
            for row in (
                db.query(Issue.issue_key)
                .filter(Issue.status != STATUS_RESOLVED)
                .filter(Issue.summary == summary)
                .filter(Issue.components == component)
                .order_by(Issue.issue_key)
                .limit(RECURRING_ERROR_SAMPLE_SIZE)
                .all()
            )
        ]

        severity = _severity_by_count(count, RECURRING_ERROR_CRITICAL_COUNT, RECURRING_ERROR_HIGH_COUNT)
        kb_article = _find_matching_kb(kb_articles, summary)

        evidence = {
            "count": count,
            "issue_keys": issue_keys,
            "component": component,
            "kb_article": kb_article.article_id if kb_article else None,
            "kb_auto_safe": bool(kb_article.x_auto_safe) if kb_article else False,
        }

        if kb_article and kb_article.x_auto_safe:
            action_type = "update_policy"
            action_label = (
                f"Allow {component} auto-remediation using {kb_article.article_id}"
            )
            # Emit the NEW blocked_components list directly (component removed),
            # so the action can be applied with a plain params merge — no
            # generator-specific "remove" instruction for the executor to parse.
            current_blocked = list(
                (auto_remediation_policy.params or {}).get("blocked_components") or []
            ) if auto_remediation_policy else []
            action_payload = {
                "policy_id": AUTO_REMEDIATION_POLICY_ID,
                "params": {
                    "blocked_components": [c for c in current_blocked if c != component]
                },
            }
        elif kb_article:
            # A KB article matches but isn't marked auto-safe — nothing to
            # automate yet, just surface the pattern.
            action_type = "none"
            action_label = f"Review {kb_article.article_id} for auto-safety"
            action_payload = None
        else:
            action_type = "create_kb"
            action_label = f"Create a KB article for: {summary}"
            action_payload = {
                "title": summary,
                "component": component,
                "sample_issue_keys": issue_keys[:3],
            }

        insights.append({
            "insight_type": "recurring_known_error",
            "title": f"Recurring issue: {summary} ({component})",
            "summary": (
                f"{count} open tickets in {component} share the summary "
                f"\"{summary}\" without being resolved."
            ),
            "severity": severity,
            "confidence": None,
            "evidence": evidence,
            "action_label": action_label,
            "action_type": action_type,
            "action_payload": action_payload,
            "computed_from": f"{total_issues} issues",
        })

    return insights


# =============================================================================
# 2. major_incident_forming
# =============================================================================


def generate_major_incident_forming(db: Session) -> list[dict]:
    """Bursts of tickets on the same component within a short time window."""
    rows = (
        db.query(Issue.issue_key, Issue.created, Issue.components, Issue.reporter)
        .filter(Issue.components.isnot(None))
        .filter(Issue.created.isnot(None))
        .all()
    )
    if not rows:
        return []

    by_component: dict[str, list[tuple[datetime, str, Optional[str]]]] = defaultdict(list)
    for issue_key, created_raw, component, reporter in rows:
        created = _parse_created(created_raw)
        if created is None:
            continue
        by_component[component].append((created, issue_key, reporter))

    window = timedelta(minutes=MAJOR_INCIDENT_WINDOW_MINUTES)
    total_issues = db.query(func.count(Issue.id)).scalar() or 0

    insights: list[dict] = []
    for component, points in by_component.items():
        clusters = _cluster_by_time_window(points, window, MAJOR_INCIDENT_MIN_COUNT)
        for cluster in clusters:
            issue_keys = [key for _, key, _ in cluster]
            reporters = {r for _, _, r in cluster if r}
            window_start = min(ts for ts, _, _ in cluster)
            window_end = max(ts for ts, _, _ in cluster)
            count = len(cluster)

            insights.append({
                "insight_type": "major_incident_forming",
                "title": f"Possible major incident forming in {component}",
                "summary": (
                    f"{count} tickets opened in {component} between "
                    f"{window_start.isoformat()} and {window_end.isoformat()} "
                    f"— a spike consistent with a single underlying cause."
                ),
                "severity": "critical",
                "confidence": None,
                "evidence": {
                    "window_start": window_start.isoformat(),
                    "window_end": window_end.isoformat(),
                    "count": count,
                    "issue_keys": issue_keys,
                    "component": component,
                    "distinct_reporters": len(reporters),
                },
                "action_label": f"Open a major incident for {component}",
                "action_type": "open_incident",
                "action_payload": {"component": component, "issue_keys": issue_keys},
                "computed_from": f"{total_issues} issues",
            })

    return insights


# =============================================================================
# 3. sla_breach_forecast
# =============================================================================


def generate_sla_breach_forecast(db: Session) -> list[dict]:
    """Assignment groups carrying enough at-risk tickets to forecast breaches."""
    at_risk_rows = (
        db.query(Issue.assignment_group, Issue.priority, Issue.issue_key)
        .filter(Issue.time_to_resolution == SLA_AT_RISK)
        .filter(Issue.assignment_group.isnot(None))
        .all()
    )
    if not at_risk_rows:
        return []

    by_group: dict[str, list[tuple[Optional[str], str]]] = defaultdict(list)
    for assignment_group, priority, issue_key in at_risk_rows:
        by_group[assignment_group].append((priority, issue_key))

    total_issues = db.query(func.count(Issue.id)).scalar() or 0

    insights: list[dict] = []
    for assignment_group, entries in by_group.items():
        count = len(entries)
        if count < SLA_FORECAST_MIN_COUNT:
            continue

        priority_breakdown = dict(Counter(p for p, _ in entries if p))
        issue_keys = [key for _, key in entries]

        already_breached_count = (
            db.query(func.count(Issue.id))
            .filter(Issue.assignment_group == assignment_group)
            .filter(Issue.time_to_resolution == SLA_BREACHED)
            .scalar()
            or 0
        )

        severity = "critical" if priority_breakdown.get(PRIORITY_HIGHEST) else "high"

        insights.append({
            "insight_type": "sla_breach_forecast",
            "title": f"{assignment_group} at risk of SLA breaches",
            "summary": (
                f"{count} tickets assigned to {assignment_group} are at risk of "
                f"breaching SLA; {already_breached_count} have already breached."
            ),
            "severity": severity,
            "confidence": None,
            "evidence": {
                "assignment_group": assignment_group,
                "at_risk_count": count,
                "already_breached_count": already_breached_count,
                "priority_breakdown": priority_breakdown,
                "issue_keys": issue_keys,
            },
            "action_label": f"Reassign or reinforce {assignment_group}",
            "action_type": "reassign",
            "action_payload": {
                "assignment_group": assignment_group,
                "at_risk_count": count,
            },
            "computed_from": f"{total_issues} issues",
        })

    return insights


# =============================================================================
# 4. automation_opportunity
# =============================================================================


def generate_automation_opportunity(db: Session) -> list[dict]:
    """Policies that escalate a lot but whose escalations mostly get approved."""
    escalation_counts = (
        db.query(PolicyEvaluation.policy_id, func.count(PolicyEvaluation.id).label("cnt"))
        .filter(PolicyEvaluation.verdict == "ESCALATE")
        .group_by(PolicyEvaluation.policy_id)
        .having(func.count(PolicyEvaluation.id) >= AUTOMATION_MIN_ESCALATIONS)
        .all()
    )
    if not escalation_counts:
        return []

    total_evaluations = db.query(func.count(PolicyEvaluation.id)).scalar() or 0
    total_workbench_items = db.query(func.count(WorkbenchItem.id)).scalar() or 0

    insights: list[dict] = []
    for policy_id, escalation_count in escalation_counts:
        evaluations = (
            db.query(PolicyEvaluation)
            .filter(PolicyEvaluation.policy_id == policy_id)
            .filter(PolicyEvaluation.verdict == "ESCALATE")
            .all()
        )

        issue_keys = {e.issue_key for e in evaluations if e.issue_key}
        workbench_items = (
            db.query(WorkbenchItem)
            .filter(WorkbenchItem.ticket_key.in_(list(issue_keys)))
            .order_by(WorkbenchItem.created_at.desc())
            .all()
            if issue_keys
            else []
        )
        # Most recent decision per ticket, in case a ticket was reviewed more than once.
        latest_decision: dict[str, WorkbenchItem] = {}
        for item in workbench_items:
            latest_decision.setdefault(item.ticket_key, item)

        approved_count = 0
        approved_confidences: list[float] = []
        sample_reasons: list[str] = []
        for evaluation in evaluations:
            decision = latest_decision.get(evaluation.issue_key)
            if decision and decision.status == WORKBENCH_APPROVED:
                approved_count += 1
                snapshot = evaluation.input_snapshot or {}
                confidence = snapshot.get("confidence")
                if isinstance(confidence, (int, float)):
                    approved_confidences.append(float(confidence))
            if evaluation.reason and len(sample_reasons) < AUTOMATION_SAMPLE_REASON_SIZE:
                sample_reasons.append(evaluation.reason)

        approval_rate = approved_count / escalation_count
        if approval_rate < AUTOMATION_APPROVAL_RATE_THRESHOLD:
            continue

        policy = db.query(Policy).filter(Policy.id == policy_id).first()
        current_params = dict(policy.params) if policy and policy.params else {}

        action_payload: Optional[dict] = None
        if approved_confidences and "min_confidence" in current_params:
            suggested = _percentile(approved_confidences, AUTOMATION_CONFIDENCE_PERCENTILE)
            suggested = max(AUTOMATION_CONFIDENCE_FLOOR, round(suggested, 2))
            action_payload = {
                "policy_id": policy_id,
                "params": {"min_confidence": suggested},
            }

        insights.append({
            "insight_type": "automation_opportunity",
            "title": f"{policy_id} may be too strict",
            "summary": (
                f"{policy_id} escalated {escalation_count} times; humans approved "
                f"{approved_count} of them ({approval_rate:.0%}). The threshold may "
                f"be too conservative."
            ),
            "severity": "high",
            "confidence": round(approval_rate, 4),
            "evidence": {
                "policy_id": policy_id,
                "escalation_count": escalation_count,
                "approved_count": approved_count,
                "approval_rate": round(approval_rate, 4),
                "current_params": current_params,
                "sample_reasons": sample_reasons,
            },
            "action_label": f"Loosen {policy_id} thresholds",
            "action_type": "update_policy",
            "action_payload": action_payload,
            "computed_from": f"{total_evaluations} policy evaluations, {total_workbench_items} workbench items",
        })

    return insights


# =============================================================================
# 5. knowledge_gap
# =============================================================================


def generate_knowledge_gap(db: Session) -> list[dict]:
    """Recurring ticket summaries with no matching KB article at all."""
    groups = (
        db.query(Issue.summary, func.count(Issue.id).label("cnt"))
        .filter(Issue.summary.isnot(None))
        .group_by(Issue.summary)
        .having(func.count(Issue.id) >= KNOWLEDGE_GAP_MIN_COUNT)
        .all()
    )
    if not groups:
        return []

    kb_articles = db.query(KnowledgeBase).all()
    total_issues = db.query(func.count(Issue.id)).scalar() or 0

    insights: list[dict] = []
    for summary, count in groups:
        if _find_matching_kb(kb_articles, summary) is not None:
            continue

        rows = (
            db.query(Issue.issue_key, Issue.components)
            .filter(Issue.summary == summary)
            .all()
        )
        issue_keys = [r[0] for r in rows]
        components = sorted({r[1] for r in rows if r[1]})

        insights.append({
            "insight_type": "knowledge_gap",
            "title": f"No knowledge base article for: {summary}",
            "summary": (
                f"{count} tickets share the summary \"{summary}\" and no existing "
                f"KB article covers it."
            ),
            "severity": "medium",
            "confidence": None,
            "evidence": {
                "summary": summary,
                "count": count,
                "issue_keys": issue_keys,
                "components": components,
            },
            "action_label": f"Create a KB article for: {summary}",
            "action_type": "create_kb",
            "action_payload": {"title": summary, "components": components},
            "computed_from": f"{total_issues} issues",
        })

    return insights


# =============================================================================
# Registry
# =============================================================================

GENERATORS: dict[str, GeneratorFn] = {
    "recurring_known_error": generate_recurring_known_error,
    "major_incident_forming": generate_major_incident_forming,
    "sla_breach_forecast": generate_sla_breach_forecast,
    "automation_opportunity": generate_automation_opportunity,
    "knowledge_gap": generate_knowledge_gap,
}
