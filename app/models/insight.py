# app/models/insight.py
"""
Insight Model — AI-generated observations about system behavior.

Insights are patterns, anomalies, and recommendations surfaced automatically
from operational data (tickets, policy evaluations, workbench outcomes).
Each insight carries a suggested action that a human can accept or dismiss.

Status lifecycle:
  open → acted
       → dismissed
"""

from sqlalchemy import Column, DateTime, Float, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB

from ..core.database import Base


class Insight(Base):
    """
    A single AI-generated insight with its supporting evidence and
    suggested action.

    Each insight represents one observation computed from operational
    data. A human can act on the suggested action or dismiss it; the
    result is recorded here and also in the audit_logs table.
    """

    __tablename__ = "insights"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)

    # What kind of observation this is
    # Values: recurring_known_error | major_incident_forming |
    #         sla_breach_forecast | automation_opportunity | knowledge_gap
    insight_type = Column(String(50), nullable=True)

    title = Column(String(500), nullable=False)
    summary = Column(Text, nullable=False)

    # Values: critical | high | medium | low
    severity = Column(String(20), nullable=True)
    confidence = Column(Float, nullable=True)

    # The records and counts it was computed from
    evidence = Column(JSONB, nullable=True)

    # Suggested action
    action_label = Column(String(500), nullable=True)  # e.g. "Lower confidence threshold to 0.70"
    # Values: update_policy | create_kb | open_incident | reassign | none
    action_type = Column(String(50), nullable=True)
    action_payload = Column(JSONB, nullable=True)  # what the action would do

    # Review lifecycle
    # Values: open | acted | dismissed
    status = Column(String(20), nullable=False, default="open", index=True)

    # Computation metadata
    computed_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    computed_from = Column(String(500), nullable=True)  # e.g. "462 issues, 1240 policy evaluations"

    def __repr__(self):
        return f"<Insight {self.id} type={self.insight_type} severity={self.severity} status={self.status}>"
