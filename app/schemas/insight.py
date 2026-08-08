# app/schemas/insight.py
"""
Pydantic schemas for AI-generated insights.
"""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel


class InsightOut(BaseModel):
    """Response schema for a single insight."""

    id: int
    insight_type: Optional[str] = None
    title: str
    summary: str
    severity: Optional[str] = None
    confidence: Optional[float] = None
    evidence: Optional[dict[str, Any]] = None
    action_label: Optional[str] = None
    action_type: Optional[str] = None
    action_payload: Optional[dict[str, Any]] = None
    status: str
    computed_at: datetime
    computed_from: Optional[str] = None

    model_config = {"from_attributes": True}


class InsightComputeResponse(BaseModel):
    """Response for POST /insights/compute — fresh insight count per type."""

    counts: dict[str, int]


class InsightActionResponse(BaseModel):
    """Response for POST /insights/{id}/act."""

    insight: InsightOut
    action_type: Optional[str] = None
    result: dict[str, Any] = {}


# ---------------------------------------------------------------------------
# Module 3: Verify Resolution
# ---------------------------------------------------------------------------

class VerifyResolutionRequest(BaseModel):
    """Request body for POST /insights/verify-resolution."""
    issue_key: str


class VerifyResolutionResponse(BaseModel):
    """Response for POST /insights/verify-resolution."""
    status: str                               # VERIFIED | ROLLBACK_EXECUTED
    issue_key: str
    probe_detail: str
    rollback_summary: Optional[str] = None
    workbench_item_id: Optional[int] = None
    policy_evaluation_id: Optional[str] = None


# ---------------------------------------------------------------------------
# Module 4: KB Authoring
# ---------------------------------------------------------------------------

class KBDraftRequest(BaseModel):
    """Request body for POST /insights/kb/draft."""
    issue_key: str


class KBDraftResponse(BaseModel):
    """Response for POST /insights/kb/draft."""
    status: str                  # DRAFTED | ALREADY_COVERED | NOT_RESOLVED | NOT_FOUND
    issue_key: str
    article_id: Optional[str] = None
    title: Optional[str] = None
    root_cause: Optional[str] = None
    workaround: Optional[str] = None
    x_auto_safe: Optional[bool] = None
    message: str


class KBApproveRequest(BaseModel):
    """Request body for POST /insights/kb/approve — commits a drafted article."""
    article_id: str
    title: Optional[str] = None
    root_cause: Optional[str] = None
    workaround: Optional[str] = None
    x_auto_safe: Optional[bool] = True
