# app/routers/workbench.py
"""
Workbench HITL (Human-in-the-Loop) endpoints.

Provides the exception queue for human review of AI-escalated tickets.

Endpoints:
  GET  /workbench/pending        → list all pending_approval items
  POST /workbench/{id}/approve   → approve an item, write audit log
  POST /workbench/{id}/reject    → reject an item, write audit log
"""

import json
import logging
from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from ..core.database import get_db
from ..models.audit import AuditCategory, AuditSeverity
from ..models.workbench import WorkbenchItem
from ..schemas.workbench import ReviewRequest, WorkbenchItemCreate, WorkbenchItemOut
from ..security import get_current_user
from ..services.audit import audit

log = logging.getLogger(__name__)

router = APIRouter(prefix="/workbench", tags=["Workbench"])


@router.post("/items", response_model=WorkbenchItemOut, status_code=201)
async def create_workbench_item(
    body: WorkbenchItemCreate,
    request: Request = None,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """
    Create a new pending approval item in the Workbench queue.
    """
    item = WorkbenchItem(
        ticket_key=body.ticket_key,
        summary=body.summary,
        reporter_name=body.reporter_name,
        reporter_email=body.reporter_email,
        vip_user=body.vip_user,
        organization=body.organization,
        priority=body.priority,
        diagnosis=body.diagnosis,
        proposed_action=body.proposed_action,
        kb_article_id=body.kb_article_id,
        status=body.status or "pending_approval",
    )
    db.add(item)
    db.commit()
    db.refresh(item)

    await audit.log(
        action="workbench.create",
        description=f"Workbench item created for review: {item.ticket_key} — {item.summary[:80]}",
        actor=user,
        category=AuditCategory.DATA,
        severity=AuditSeverity.INFO,
        resource_type="workbench_item",
        resource_id=str(item.id),
        resource_name=item.ticket_key,
        request=request,
        success=True,
    )

    log.info(f"✨ Created Workbench item {item.ticket_key} (ID: {item.id})")
    return item


@router.post("/webhook", response_model=WorkbenchItemOut, status_code=201)
@router.post("/supervity-webhook", response_model=WorkbenchItemOut, status_code=201)
async def supervity_webhook_item(
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Webhook endpoint for Supervity Auto orchestrator runs to directly push
    tasks requiring human operator review into the Command Center Workbench queue.
    """
    try:
        body_bytes = await request.body()
        data = json.loads(body_bytes.decode("utf-8")) if body_bytes else {}
    except Exception:
        data = {}

    ticket_key = data.get("ticket_key") or data.get("issue_key") or data.get("id") or "SUPERVITY-AUTO"
    summary = data.get("summary") or data.get("title") or data.get("message") or "Supervity Auto Task Exception"
    reporter_email = data.get("reporter_email") or data.get("email") or "auto@supervity.ai"
    reporter_name = data.get("reporter_name") or data.get("user") or "Supervity Auto"
    priority = data.get("priority") or "High"
    diagnosis = data.get("diagnosis") or data.get("reason") or "Supervity Auto workflow execution requires human review."
    proposed_action = data.get("proposed_action") or data.get("action") or f"Human Operator Approval for {ticket_key}"

    item = WorkbenchItem(
        ticket_key=ticket_key,
        summary=summary,
        reporter_name=reporter_name,
        reporter_email=reporter_email,
        vip_user=bool(data.get("vip_user") or data.get("is_vip", False)),
        organization=data.get("organization") or "Supervity Auto",
        priority=priority,
        diagnosis=diagnosis,
        proposed_action=proposed_action,
        kb_article_id=data.get("kb_article_id"),
        status="pending_approval",
    )
    db.add(item)
    db.commit()
    db.refresh(item)

    log.info(f"✨ Supervity Auto Webhook created Workbench item {item.ticket_key} (ID: {item.id})")
    return item


@router.get("/pending", response_model=List[WorkbenchItemOut])
async def get_pending_items(
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """
    Return all workbench items with status = 'pending_approval'.

    These are tickets that the AI agent escalated for human review —
    either because the reporter is a VIP, the SLA is at risk, or
    the required action exceeds the agent's auto-safe threshold.
    """
    items = (
        db.query(WorkbenchItem)
        .filter(WorkbenchItem.status == "pending_approval")
        .order_by(WorkbenchItem.created_at.desc())
        .all()
    )
    log.info(f"Workbench pending: {len(items)} items returned for {user.get('email', 'unknown')}")
    return items


@router.post("/{item_id}/approve", response_model=WorkbenchItemOut)
async def approve_item(
    item_id: int,
    body: ReviewRequest = ReviewRequest(),
    request: Request = None,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """
    Approve a workbench item.

    - Sets status to 'approved'
    - Records who approved it and when
    - Writes an entry to the audit log
    """
    item = db.query(WorkbenchItem).filter(WorkbenchItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail=f"Workbench item {item_id} not found")

    if item.status != "pending_approval":
        raise HTTPException(
            status_code=409,
            detail=f"Item {item_id} is already '{item.status}' and cannot be approved",
        )

    reviewer = body.reviewed_by or user.get("email") or user.get("preferred_username") or "unknown"

    item.status = "approved"
    item.reviewed_by = reviewer
    item.reviewed_at = datetime.now(timezone.utc)
    item.review_note = body.note

    db.commit()
    db.refresh(item)

    # Audit log
    await audit.log(
        action="workbench.approve",
        description=(
            f"Workbench item approved: {item.ticket_key} — {item.summary[:80]}. "
            f"Reviewer: {reviewer}. Note: {body.note or 'none'}."
        ),
        actor=user,
        category=AuditCategory.DATA,
        severity=AuditSeverity.INFO,
        resource_type="workbench_item",
        resource_id=str(item_id),
        resource_name=item.ticket_key,
        metadata={
            "ticket_key": item.ticket_key,
            "vip_user": item.vip_user,
            "organization": item.organization,
            "priority": item.priority,
            "kb_article_id": item.kb_article_id,
            "review_note": body.note,
        },
        request=request,
        success=True,
    )

    log.info(f"✅ Workbench {item.ticket_key} APPROVED by {reviewer}")
    return item


@router.post("/{item_id}/reject", response_model=WorkbenchItemOut)
async def reject_item(
    item_id: int,
    body: ReviewRequest = ReviewRequest(),
    request: Request = None,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """
    Reject a workbench item.

    - Sets status to 'rejected'
    - Records who rejected it and when
    - Writes an entry to the audit log
    """
    item = db.query(WorkbenchItem).filter(WorkbenchItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail=f"Workbench item {item_id} not found")

    if item.status != "pending_approval":
        raise HTTPException(
            status_code=409,
            detail=f"Item {item_id} is already '{item.status}' and cannot be rejected",
        )

    reviewer = body.reviewed_by or user.get("email") or user.get("preferred_username") or "unknown"

    item.status = "rejected"
    item.reviewed_by = reviewer
    item.reviewed_at = datetime.now(timezone.utc)
    item.review_note = body.note

    db.commit()
    db.refresh(item)

    # Audit log
    await audit.log(
        action="workbench.reject",
        description=(
            f"Workbench item rejected: {item.ticket_key} — {item.summary[:80]}. "
            f"Reviewer: {reviewer}. Note: {body.note or 'none'}."
        ),
        actor=user,
        category=AuditCategory.DATA,
        severity=AuditSeverity.WARNING,
        resource_type="workbench_item",
        resource_id=str(item_id),
        resource_name=item.ticket_key,
        metadata={
            "ticket_key": item.ticket_key,
            "vip_user": item.vip_user,
            "organization": item.organization,
            "priority": item.priority,
            "kb_article_id": item.kb_article_id,
            "review_note": body.note,
        },
        request=request,
        success=True,
    )

    log.info(f"❌ Workbench {item.ticket_key} REJECTED by {reviewer}")
    return item
