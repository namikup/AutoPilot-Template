# app/models/workbench.py
"""
WorkbenchItem Model — Human-in-the-Loop exception queue.

When an AI agent encounters an exception it cannot auto-resolve
(e.g. VIP ticket near SLA breach, missing KB article, policy violation),
it creates a WorkbenchItem for human review.

Status lifecycle:
  pending_approval → approved
                   → rejected
"""

from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text, func

from ..core.database import Base


class WorkbenchItem(Base):
    """
    Exception queue item awaiting human approval.

    Each item represents one escalated case. After a human
    approves or rejects it, the result is written back here
    and also recorded in the audit_logs table.
    """

    __tablename__ = "workbench_items"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)

    # Source ticket
    ticket_key = Column(String(50), nullable=False, index=True)    # e.g. ITSM-2013
    summary = Column(String(500), nullable=False)                   # ticket title
    reporter_email = Column(String(255), nullable=True)
    reporter_name = Column(String(255), nullable=True)
    vip_user = Column(Boolean, nullable=False, default=False)       # True → VIP escalation
    organization = Column(String(255), nullable=True)
    priority = Column(String(50), nullable=True)

    # AI diagnosis
    diagnosis = Column(Text, nullable=True)        # what the agent determined
    proposed_action = Column(Text, nullable=True)  # what the agent recommends

    # Linked KB article (if any)
    kb_article_id = Column(String(50), nullable=True)   # e.g. KB-103

    # Review lifecycle
    # Values: pending_approval | approved | rejected
    status = Column(String(50), nullable=False, default="pending_approval", index=True)
    reviewed_by = Column(String(255), nullable=True)     # email of reviewer
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    review_note = Column(Text, nullable=True)             # optional note from reviewer

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    def __repr__(self):
        return f"<WorkbenchItem {self.ticket_key} status={self.status}>"
