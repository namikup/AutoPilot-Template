"""Add insights table

Revision ID: f6g7h8i9j0k1
Revises: e5f6g7h8i9j0
Create Date: 2026-08-06 00:00:00.000000

Creates:
  - insights   (AI-generated observations: patterns, anomalies, recommendations)
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "f6g7h8i9j0k1"
down_revision: Union[str, None] = "e5f6g7h8i9j0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "insights",
        sa.Column("id", sa.Integer(), nullable=False, autoincrement=True),
        sa.Column("insight_type", sa.String(50), nullable=True),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("severity", sa.String(20), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("evidence", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("action_label", sa.String(500), nullable=True),
        sa.Column("action_type", sa.String(50), nullable=True),
        sa.Column("action_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="open"),
        sa.Column(
            "computed_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("computed_from", sa.String(500), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_insights_id", "insights", ["id"], unique=False)
    op.create_index("ix_insights_status", "insights", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_insights_status", table_name="insights")
    op.drop_index("ix_insights_id", table_name="insights")
    op.drop_table("insights")
