# app/schemas/workbench.py
"""
Pydantic schemas for the Workbench HITL endpoints.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class WorkbenchItemOut(BaseModel):
    """Response schema for a single workbench queue item."""

    id: int
    ticket_key: str
    summary: str
    reporter_email: Optional[str] = None
    reporter_name: Optional[str] = None
    vip_user: bool
    organization: Optional[str] = None
    priority: Optional[str] = None
    diagnosis: Optional[str] = None
    proposed_action: Optional[str] = None
    kb_article_id: Optional[str] = None
    status: str
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    review_note: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ReviewRequest(BaseModel):
    """Optional body for approve / reject endpoints."""

    note: Optional[str] = None   # human reviewer's note
    reviewed_by: Optional[str] = None  # reviewer identifier (email or name)


class WorkbenchItemCreate(BaseModel):
    """Payload to create a new pending approval item in the Workbench queue."""

    ticket_key: str
    summary: str
    reporter_name: Optional[str] = None
    reporter_email: Optional[str] = None
    vip_user: bool = False
    organization: Optional[str] = None
    priority: Optional[str] = "High"
    diagnosis: Optional[str] = None
    proposed_action: Optional[str] = None
    kb_article_id: Optional[str] = None
    status: Optional[str] = "pending_approval"

