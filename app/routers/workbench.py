# app/routers/workbench.py
"""
Workbench HITL (Human-in-the-Loop) endpoints.

Provides the exception queue for human review of AI-escalated tickets.

Endpoints:
  GET  /workbench/pending        → list all pending_approval items
  POST /workbench/{id}/approve   → approve an item, write audit log
  POST /workbench/{id}/reject    → reject an item, write audit log
"""

import logging
from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from ..core.database import get_db
from ..models.audit import AuditCategory, AuditSeverity
from ..models.workbench import WorkbenchItem
from ..schemas.workbench import ReviewRequest, WorkbenchItemOut
from ..security import get_current_user
from ..services.audit import audit

log = logging.getLogger(__name__)

router = APIRouter(prefix="/workbench", tags=["Workbench"])


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
