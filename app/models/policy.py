# app/models/policy.py
"""
Policy models — AI governance rules and their evaluation audit trail.

  policies             — editable rules that constrain AI agent behavior
  policy_evaluations   — immutable log of the verdict produced each time
                          an agent run consulted a policy for an issue
"""

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB

from ..core.database import Base


class Policy(Base):
    """
    An AI governance policy with editable, versioned parameters.

    id is a human-readable slug (e.g. "AUTO_REMEDIATION_SAFETY") rather than
    an auto-incrementing integer, since policies are referenced by name
    from agent configuration and evaluation records.
    """

    __tablename__ = "policies"

    id = Column(String(100), primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    category = Column(String(100), nullable=True)
    enabled = Column(Boolean, nullable=False, default=True)
    priority = Column(Integer, nullable=False, default=100)  # lower = evaluated first
    params = Column(JSONB, nullable=False)  # editable thresholds
    version = Column(Integer, nullable=False, default=1)
    updated_by = Column(String(255), nullable=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    def __repr__(self):
        return f"<Policy {self.id} v{self.version} enabled={self.enabled}>"


class PolicyEvaluation(Base):
    """
    Immutable record of a single policy evaluation during an agent run.

    Captures the exact params and input that produced the verdict, so a
    past decision can be explained even after the policy is later edited.
    """

    __tablename__ = "policy_evaluations"

    id = Column(String(100), primary_key=True, index=True)

    run_id = Column(String(100), nullable=True, index=True)
    issue_key = Column(String(50), nullable=True, index=True)

    policy_id = Column(String(100), ForeignKey("policies.id"), nullable=False, index=True)
    policy_version = Column(Integer, nullable=True)

    verdict = Column(String(20), nullable=True)  # ALLOW / ESCALATE / DENY
    reason = Column(Text, nullable=True)

    input_snapshot = Column(JSONB, nullable=True)
    params_used = Column(JSONB, nullable=True)

    evaluated_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    def __repr__(self):
        return f"<PolicyEvaluation {self.id} policy={self.policy_id} verdict={self.verdict}>"
