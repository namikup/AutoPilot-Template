# app/schemas/policy.py
"""
Pydantic schemas for the AI Policy governance endpoints.
"""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class PolicyOut(BaseModel):
    """Response schema for a single policy."""

    id: str
    name: str
    description: Optional[str] = None
    category: Optional[str] = None
    enabled: bool
    priority: int
    params: dict[str, Any]
    version: int
    updated_by: Optional[str] = None
    updated_at: datetime

    model_config = {"from_attributes": True}


class PolicyUpdate(BaseModel):
    """Request body for updating a policy — only fields provided are changed."""

    name: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    enabled: Optional[bool] = None
    priority: Optional[int] = None
    params: Optional[dict[str, Any]] = None
    updated_by: Optional[str] = None


class PolicyEvaluationOut(BaseModel):
    """Response schema for a single policy evaluation record."""

    id: str
    run_id: Optional[str] = None
    issue_key: Optional[str] = None
    policy_id: str
    policy_version: Optional[int] = None
    verdict: Optional[str] = None
    reason: Optional[str] = None
    input_snapshot: Optional[dict[str, Any]] = None
    params_used: Optional[dict[str, Any]] = None
    evaluated_at: datetime

    model_config = {"from_attributes": True}


class PolicyEvaluateRequest(BaseModel):
    """
    Request context evaluated against every enabled policy.

    Every business field is optional (aside from the run/issue correlation
    IDs) — a rule that needs a field which wasn't supplied is expected to
    ESCALATE, not crash. See app/services/policy_rules.py.
    """

    run_id: str
    issue_key: str
    action: Optional[str] = None
    kb_article: Optional[str] = None
    kb_auto_safe: Optional[bool] = None
    confidence: Optional[float] = None
    priority: Optional[str] = None
    is_vip: Optional[bool] = None
    region: Optional[str] = None
    sla_remaining_pct: Optional[float] = None
    sla_status: Optional[str] = None
    change_required: Optional[bool] = None
    cab_approval_required: Optional[bool] = None
    risk: Optional[str] = None
    is_rollback: Optional[bool] = None
    is_reopened: Optional[bool] = None
    inactive_hours: Optional[float] = None
    component: Optional[str] = None
    x_channel: Optional[str] = None
    reporter: Optional[str] = None


class PolicyEvaluateResponse(BaseModel):
    """Aggregate result of evaluating all enabled policies for one request."""

    verdict: str = Field(..., description="ALLOW | ESCALATE | DENY")
    reason: str
    evaluations: list[PolicyEvaluationOut]
