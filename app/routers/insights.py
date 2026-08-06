# app/routers/insights.py
"""
AI Insights endpoints.

Provides the visibility layer: compute fresh insights from operational
data, list them, and act on or dismiss the ones a human reviews.

Endpoints:
  POST /insights/compute       → run every generator, refresh open insights
  GET  /insights                → list insights, newest first
  POST /insights/{id}/act       → execute an insight's suggested action
  POST /insights/{id}/dismiss   → dismiss an insight
"""

import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from ..core.database import get_db
from ..models.audit import AuditCategory, AuditSeverity
from ..models.insight import Insight
from ..models.policy import Policy
from ..schemas.insight import InsightActionResponse, InsightComputeResponse, InsightOut
from ..security import get_current_user
from ..services.audit import audit
from ..services.insight_engine import GENERATORS

log = logging.getLogger(__name__)

router = APIRouter(prefix="/insights", tags=["Insights"])


@router.post("/compute", response_model=InsightComputeResponse)
async def compute_insights(
    request: Request = None,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """
    Run every insight generator.

    For each insight type, prior insights still 'open' are cleared and
    replaced with the freshly computed set. Insights already 'acted' or
    'dismissed' are left untouched — this only refreshes the open queue.
    """
    counts: dict[str, int] = {}

    for insight_type, generate in GENERATORS.items():
        db.query(Insight).filter(
            Insight.insight_type == insight_type,
            Insight.status == "open",
        ).delete(synchronize_session=False)

        fresh = generate(db)
        for insight_dict in fresh:
            db.add(Insight(**insight_dict))

        counts[insight_type] = len(fresh)

    db.commit()

    # Audit log
    await audit.log(
        action="insight.compute",
        description=f"Computed insights: {counts}",
        actor=user,
        category=AuditCategory.DATA,
        severity=AuditSeverity.INFO,
        resource_type="insight",
        metadata={"counts": counts},
        request=request,
        success=True,
    )

    log.info(f"Insight compute run: {counts}")
    return InsightComputeResponse(counts=counts)


@router.get("", response_model=List[InsightOut])
async def list_insights(
    severity: Optional[str] = Query(None, description="Filter by severity"),
    insight_type: Optional[str] = Query(None, description="Filter by insight type"),
    status: Optional[str] = Query(None, description="Filter by status"),
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Return insights, newest first, optionally filtered."""
    query = db.query(Insight)
    if severity:
        query = query.filter(Insight.severity == severity)
    if insight_type:
        query = query.filter(Insight.insight_type == insight_type)
    if status:
        query = query.filter(Insight.status == status)

    insights = query.order_by(Insight.computed_at.desc()).all()
    return insights


@router.post("/{insight_id}/act", response_model=InsightActionResponse)
async def act_on_insight(
    insight_id: int,
    request: Request = None,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """
    Execute an insight's suggested action.

    - action_type == "update_policy": merges action_payload["params"] onto
      the referenced policy's current params, bumps its version, and
      stamps updated_by.
    - Any other action_type: for now, just marks the insight 'acted' —
      concretely executing create_kb / open_incident / reassign is a
      future integration.
    """
    insight = db.query(Insight).filter(Insight.id == insight_id).first()
    if not insight:
        raise HTTPException(status_code=404, detail=f"Insight {insight_id} not found")

    if insight.status != "open":
        raise HTTPException(
            status_code=409,
            detail=f"Insight {insight_id} is already '{insight.status}' and cannot be acted on",
        )

    actor_name = user.get("email") or user.get("preferred_username") or "unknown"
    result: dict = {}

    if insight.action_type == "update_policy" and insight.action_payload:
        policy_id = insight.action_payload.get("policy_id")
        new_params = insight.action_payload.get("params") or {}
        policy = db.query(Policy).filter(Policy.id == policy_id).first() if policy_id else None

        if not policy:
            raise HTTPException(
                status_code=404,
                detail=f"Policy '{policy_id}' referenced by insight {insight_id} not found",
            )

        policy.params = {**(policy.params or {}), **new_params}
        policy.version += 1
        policy.updated_by = actor_name

        result = {
            "policy_id": policy.id,
            "new_version": policy.version,
            "params": policy.params,
        }

    insight.status = "acted"

    db.commit()
    db.refresh(insight)

    # Audit log
    await audit.log(
        action="insight.act",
        description=(
            f"Insight {insight_id} acted on ({insight.action_type}) by {actor_name}: {insight.title}"
        ),
        actor=user,
        category=AuditCategory.DATA,
        severity=AuditSeverity.INFO,
        resource_type="insight",
        resource_id=str(insight_id),
        resource_name=insight.title,
        metadata={"action_type": insight.action_type, "result": result},
        request=request,
        success=True,
    )

    log.info(f"✅ Insight {insight_id} acted on ({insight.action_type}) by {actor_name}")
    return InsightActionResponse(insight=insight, action_type=insight.action_type, result=result)


@router.post("/{insight_id}/dismiss", response_model=InsightOut)
async def dismiss_insight(
    insight_id: int,
    request: Request = None,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Dismiss an insight without acting on it."""
    insight = db.query(Insight).filter(Insight.id == insight_id).first()
    if not insight:
        raise HTTPException(status_code=404, detail=f"Insight {insight_id} not found")

    if insight.status != "open":
        raise HTTPException(
            status_code=409,
            detail=f"Insight {insight_id} is already '{insight.status}' and cannot be dismissed",
        )

    actor_name = user.get("email") or user.get("preferred_username") or "unknown"
    insight.status = "dismissed"

    db.commit()
    db.refresh(insight)

    # Audit log
    await audit.log(
        action="insight.dismiss",
        description=f"Insight {insight_id} dismissed by {actor_name}: {insight.title}",
        actor=user,
        category=AuditCategory.DATA,
        severity=AuditSeverity.WARNING,
        resource_type="insight",
        resource_id=str(insight_id),
        resource_name=insight.title,
        request=request,
        success=True,
    )

    log.info(f"❌ Insight {insight_id} dismissed by {actor_name}")
    return insight
