# app/routers/policies.py
"""
AI Policy governance endpoints.

Provides the policy engine's public surface: evaluate a request context
against every enabled policy, inspect/update policies, and review the
resulting evaluation audit trail.

Endpoints:
  POST  /policies/evaluate      → run every enabled policy against a
                                   request context, write the audit trail
  GET   /policies                → list all policies
  GET   /policies/evaluations    → recent policy_evaluations, filterable
  GET   /policies/{id}           → a single policy
  PATCH /policies/{id}           → update params/enabled, bumps version
"""

import logging
import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from ..core.database import get_db
from ..models.audit import AuditCategory, AuditSeverity
from ..models.policy import Policy, PolicyEvaluation
from ..models.workbench import WorkbenchItem
from ..models.hackathon import Issue
from ..schemas.policy import (
    PolicyEvaluateRequest,
    PolicyEvaluateResponse,
    PolicyEvaluationOut,
    PolicyOut,
    PolicyUpdate,
)
from ..security import get_current_user
from ..services.audit import audit
from ..services.policy_rules import RULES

log = logging.getLogger(__name__)

router = APIRouter(prefix="/policies", tags=["Policies"])


@router.get("", response_model=List[PolicyOut])
async def list_policies(
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """
    Return all policies, ordered by evaluation priority (ascending).
    """
    policies = db.query(Policy).order_by(Policy.priority.asc()).all()
    return policies


@router.post("/evaluate", response_model=PolicyEvaluateResponse)
async def evaluate_policies(
    payload: PolicyEvaluateRequest,
    request: Request = None,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """
    Evaluate every enabled policy (priority ascending) against the given
    request context.

    - Writes one policy_evaluations row for every policy actually
      evaluated (pass or fail), capturing the policy's version and
      params at the moment of evaluation — so a past decision can be
      explained even after the policy is later edited.
    - DENY short-circuits: evaluation stops at the first DENY.
    - ESCALATE does not short-circuit: evaluation continues so the
      Workbench item carries every reason a human should see.
    - Automatically creates a WorkbenchItem if final_verdict is ESCALATE or DENY and
      payload.auto_route_workbench is True.
    """
    req = payload.model_dump()

    policies = (
        db.query(Policy)
        .filter(Policy.enabled == True)  # noqa: E712 — matches repo convention (see audit.py)
        .order_by(Policy.priority.asc())
        .all()
    )

    saved_evaluations: list[PolicyEvaluation] = []
    escalate_reasons: list[str] = []
    final_verdict = "ALLOW"
    final_reason = "All active policies passed."

    for policy in policies:
        rule_fn = RULES.get(policy.id)
        if rule_fn is None:
            log.warning(f"No rule implementation registered for policy '{policy.id}'; skipping")
            continue

        verdict, reason = rule_fn(req, policy.params or {})

        evaluation = PolicyEvaluation(
            id=str(uuid.uuid4()),
            run_id=payload.run_id,
            issue_key=payload.issue_key,
            policy_id=policy.id,
            policy_version=policy.version,
            verdict=verdict,
            reason=reason,
            input_snapshot=req,
            params_used=policy.params,
        )
        db.add(evaluation)
        saved_evaluations.append(evaluation)

        if verdict == "DENY":
            final_verdict = "DENY"
            final_reason = reason
            break
        elif verdict == "ESCALATE":
            final_verdict = "ESCALATE"
            escalate_reasons.append(f"[{policy.id}] {reason}")

    if final_verdict == "ESCALATE":
        final_reason = " | ".join(escalate_reasons)

    wb_item_id: Optional[str] = None
    if payload.auto_route_workbench and final_verdict in ["ESCALATE", "DENY"]:
        existing_item = (
            db.query(WorkbenchItem)
            .filter(
                WorkbenchItem.ticket_key == payload.issue_key,
                WorkbenchItem.status == "pending_approval",
            )
            .first()
        )
        if existing_item:
            wb_item_id = str(existing_item.id)
        else:
            issue_obj = db.query(Issue).filter(Issue.issue_key == payload.issue_key).first()
            new_item = WorkbenchItem(
                ticket_key=payload.issue_key,
                summary=issue_obj.summary if issue_obj else f"Policy Exception: {payload.issue_key}",
                reporter_name=issue_obj.reporter if issue_obj else (payload.reporter or "System"),
                reporter_email=payload.reporter or "user@example.com",
                vip_user=payload.is_vip or (issue_obj.reporter in ["Faizal Das", "Tariq Lim", "Aisha Lim"] if issue_obj else False),
                organization=issue_obj.organizations if issue_obj else None,
                priority=payload.priority or (issue_obj.priority if issue_obj else "High"),
                diagnosis=f"Policy Escalation: {final_reason}",
                proposed_action=f"Human Approval Required — Policy Verdict: {final_verdict}",
                kb_article_id=payload.kb_article,
                status="pending_approval",
            )
            db.add(new_item)
            db.flush()
            wb_item_id = str(new_item.id)
            log.info(f"🚨 Auto-created WorkbenchItem ID {wb_item_id} for {payload.issue_key} due to {final_verdict}")

    db.commit()
    for evaluation in saved_evaluations:
        db.refresh(evaluation)

    # Audit log
    await audit.log(
        action="policy.evaluate",
        description=(
            f"Policy evaluation for {payload.issue_key} (run {payload.run_id}): "
            f"{final_verdict} — {final_reason}"
        ),
        actor=user,
        category=AuditCategory.DATA,
        severity=AuditSeverity.INFO if final_verdict == "ALLOW" else AuditSeverity.WARNING,
        resource_type="issue",
        resource_id=payload.issue_key,
        resource_name=payload.issue_key,
        metadata={
            "run_id": payload.run_id,
            "verdict": final_verdict,
            "policies_evaluated": [e.policy_id for e in saved_evaluations],
            "workbench_item_id": wb_item_id,
        },
        request=request,
        success=True,
    )

    log.info(
        f"Policy evaluation for {payload.issue_key} (run {payload.run_id}): "
        f"{final_verdict} across {len(saved_evaluations)} polic"
        f"{'y' if len(saved_evaluations) == 1 else 'ies'}"
    )

    return PolicyEvaluateResponse(
        verdict=final_verdict,
        reason=final_reason,
        evaluations=[PolicyEvaluationOut.model_validate(e) for e in saved_evaluations],
        workbench_item_id=wb_item_id,
    )


@router.get("/evaluations", response_model=List[PolicyEvaluationOut])
async def list_evaluations(
    issue_key: Optional[str] = Query(None, description="Filter by issue key"),
    limit: int = Query(50, ge=1, le=500, description="Max rows to return"),
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """
    Return recent policy evaluations, newest first.

    NOTE: This route is registered before GET /{policy_id} so that
    "/evaluations" isn't swallowed as a policy_id path parameter.
    """
    query = db.query(PolicyEvaluation)
    if issue_key:
        query = query.filter(PolicyEvaluation.issue_key == issue_key)

    evaluations = (
        query.order_by(PolicyEvaluation.evaluated_at.desc())
        .limit(limit)
        .all()
    )
    return evaluations


@router.get("/{policy_id}", response_model=PolicyOut)
async def get_policy(
    policy_id: str,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Get a single policy by id."""
    policy = db.query(Policy).filter(Policy.id == policy_id).first()
    if not policy:
        raise HTTPException(status_code=404, detail=f"Policy '{policy_id}' not found")
    return policy


@router.patch("/{policy_id}", response_model=PolicyOut)
async def update_policy(
    policy_id: str,
    payload: PolicyUpdate,
    request: Request = None,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """
    Update a policy's editable fields (name, description, category,
    enabled, priority, params).

    - Sets the changed fields
    - Bumps `version` by 1
    - Stamps `updated_by` from the current user (or the request body,
      if explicitly provided)
    - Writes an entry to the audit log
    """
    policy = db.query(Policy).filter(Policy.id == policy_id).first()
    if not policy:
        raise HTTPException(status_code=404, detail=f"Policy '{policy_id}' not found")

    updates = payload.model_dump(exclude_unset=True, exclude={"updated_by"})
    if not updates:
        raise HTTPException(status_code=400, detail="No fields provided to update")

    for field, value in updates.items():
        setattr(policy, field, value)

    policy.version += 1
    policy.updated_by = (
        payload.updated_by
        or user.get("email")
        or user.get("preferred_username")
        or "unknown"
    )

    db.commit()
    db.refresh(policy)

    # Audit log
    await audit.log(
        action="policy.update",
        description=f"Policy '{policy.id}' updated to v{policy.version} by {policy.updated_by}",
        actor=user,
        category=AuditCategory.SETTINGS,
        severity=AuditSeverity.INFO,
        resource_type="policy",
        resource_id=policy.id,
        resource_name=policy.name,
        metadata={"changed_fields": list(updates.keys()), "new_version": policy.version},
        request=request,
        success=True,
    )

    log.info(f"Policy '{policy.id}' updated to v{policy.version} by {policy.updated_by}")
    return policy
