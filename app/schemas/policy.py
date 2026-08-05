# app/schemas/policy.py
"""
Pydantic schemas for AI governance policies and their evaluation audit trail.
"""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class PolicyBase(BaseModel):
    name: str
    description: Optional[str] = None
    category: Optional[str] = None
    enabled: bool = True
    priority: int = 100
    params: dict[str, Any] = Field(..., description="Editable thresholds for this policy")


class PolicyCreate(PolicyBase):
    id: str = Field(..., description="Human-readable policy slug, e.g. AUTO_REMEDIATION_SAFETY")


class PolicyUpdate(BaseModel):
    """Partial update — only fields provided are changed."""

    name: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    enabled: Optional[bool] = None
    priority: Optional[int] = None
    params: Optional[dict[str, Any]] = None
    updated_by: Optional[str] = None


class PolicyOut(PolicyBase):
    id: str
    version: int
    updated_by: Optional[str] = None
    updated_at: datetime

    model_config = {"from_attributes": True}


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
