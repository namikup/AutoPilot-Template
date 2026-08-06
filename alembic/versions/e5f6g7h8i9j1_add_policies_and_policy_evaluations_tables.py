"""Add policies and policy_evaluations tables

Revision ID: e5f6g7h8i9j0
Revises: d4e5f6g7h8i9
Create Date: 2026-08-06 00:00:00.000000

Creates:
  - policies              (AI governance policies with editable params)
  - policy_evaluations    (audit trail of policy verdicts per agent run)
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "e5f6g7h8i9j1"
down_revision: Union[str, None] = "e5f6g7h8i9j0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # =========================================================================
    # policies
    # =========================================================================
    op.create_table(
        "policies",
        sa.Column("id", sa.String(100), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("category", sa.String(100), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("params", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("updated_by", sa.String(255), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=True,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_policies_id", "policies", ["id"], unique=False)

    # =========================================================================
    # policy_evaluations
    # =========================================================================
    op.create_table(
        "policy_evaluations",
        sa.Column("id", sa.String(100), nullable=False),
        sa.Column("run_id", sa.String(100), nullable=True),
        sa.Column("issue_key", sa.String(50), nullable=True),
        sa.Column("policy_id", sa.String(100), nullable=False),
        sa.Column("policy_version", sa.Integer(), nullable=True),
        sa.Column("verdict", sa.String(20), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("input_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("params_used", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "evaluated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["policy_id"], ["policies.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_policy_evaluations_id", "policy_evaluations", ["id"], unique=False)
    op.create_index("ix_policy_evaluations_run_id", "policy_evaluations", ["run_id"], unique=False)
    op.create_index("ix_policy_evaluations_issue_key", "policy_evaluations", ["issue_key"], unique=False)
    op.create_index("ix_policy_evaluations_policy_id", "policy_evaluations", ["policy_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_policy_evaluations_policy_id", table_name="policy_evaluations")
    op.drop_index("ix_policy_evaluations_issue_key", table_name="policy_evaluations")
    op.drop_index("ix_policy_evaluations_run_id", table_name="policy_evaluations")
    op.drop_index("ix_policy_evaluations_id", table_name="policy_evaluations")
    op.drop_table("policy_evaluations")

    op.drop_index("ix_policies_id", table_name="policies")
    op.drop_table("policies")
