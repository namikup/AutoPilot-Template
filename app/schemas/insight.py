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
