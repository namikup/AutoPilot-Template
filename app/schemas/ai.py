# app/schemas/ai.py
"""
Pydantic schemas for AI Manager chat requests and Supervity workflow responses.
"""

from typing import Any, Optional
from pydantic import BaseModel, Field


class AIChatRequest(BaseModel):
    message: str = Field(..., description="User prompt/message or ticket description")
    history: Optional[list[dict[str, Any]]] = Field(
        default=[], description="Chat message history list"
    )
    context: Optional[dict[str, Any]] = Field(
        default={}, description="Current page context"
    )

    # Optional Supervity workflow inputs
    issue_key: Optional[str] = Field(
        default="ISSUE-101", description="Ticket issue key"
    )
    reporter_email: Optional[str] = Field(
        default="user@example.com", description="Reporter email address"
    )
    inactive_days_threshold: Optional[int] = Field(
        default=7, description="Inactive days threshold"
    )
    sla_threshold_hours: Optional[int] = Field(
        default=24, description="SLA threshold in hours"
    )
    it_team_slack: Optional[str] = Field(
        default="#it-support", description="IT support Slack channel"
    )


class AIChatResponse(BaseModel):
    response: str = Field(..., description="AI generated message response")
    status: str = Field(default="success", description="Response status")
    workflow_id: Optional[str] = Field(
        default=None, description="Executed workflow ID"
    )
    tool_calls: Optional[list[dict[str, Any]]] = Field(
        default=None, description="Optional tool call responses"
    )
