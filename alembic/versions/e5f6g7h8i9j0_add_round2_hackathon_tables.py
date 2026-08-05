"""Add Round 2 hackathon tables and columns

Revision ID: e5f6g7h8i9j0
Revises: d4e5f6g7h8i9
Create Date: 2026-08-06 00:16:00.000000

Adds:
  - New columns to issues (x_channel, x_escalation_risk, x_reopened, first_response_time, linked_incident, x_confidence)
  - ticket_comments
  - csat_surveys
  - change_requests
  - incident_problem_links
  - sla_calendar
  - team_roster
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "e5f6g7h8i9j0"
down_revision: Union[str, None] = "d4e5f6g7h8i9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add new columns to issues
    op.add_column("issues", sa.Column("x_channel", sa.String(50), nullable=True))
    op.add_column("issues", sa.Column("x_escalation_risk", sa.String(50), nullable=True))
    op.add_column("issues", sa.Column("x_reopened", sa.Boolean(), nullable=False, server_default="false"))
    op.add_column("issues", sa.Column("first_response_time", sa.String(50), nullable=True))
    op.add_column("issues", sa.Column("linked_incident", sa.String(50), nullable=True))
    op.add_column("issues", sa.Column("x_confidence", sa.Float(), nullable=True))
    op.create_index("ix_issues_linked_incident", "issues", ["linked_incident"], unique=False)

    # 2. ticket_comments
    op.create_table(
        "ticket_comments",
        sa.Column("id", sa.Integer(), nullable=False, autoincrement=True),
        sa.Column("comment_id", sa.String(50), nullable=False),
        sa.Column("issue_key", sa.String(50), nullable=False),
        sa.Column("author", sa.String(255), nullable=True),
        sa.Column("created", sa.String(50), nullable=True),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("is_internal", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("ingested_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ticket_comments_id", "ticket_comments", ["id"], unique=False)
    op.create_index("ix_ticket_comments_comment_id", "ticket_comments", ["comment_id"], unique=True)
    op.create_index("ix_ticket_comments_issue_key", "ticket_comments", ["issue_key"], unique=False)

    # 3. csat_surveys
    op.create_table(
        "csat_surveys",
        sa.Column("id", sa.Integer(), nullable=False, autoincrement=True),
        sa.Column("survey_id", sa.String(50), nullable=False),
        sa.Column("issue_key", sa.String(50), nullable=False),
        sa.Column("score", sa.Integer(), nullable=True),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("submitted_at", sa.String(50), nullable=True),
        sa.Column("ingested_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_csat_surveys_id", "csat_surveys", ["id"], unique=False)
    op.create_index("ix_csat_surveys_survey_id", "csat_surveys", ["survey_id"], unique=True)
    op.create_index("ix_csat_surveys_issue_key", "csat_surveys", ["issue_key"], unique=False)

    # 4. change_requests
    op.create_table(
        "change_requests",
        sa.Column("id", sa.Integer(), nullable=False, autoincrement=True),
        sa.Column("change_id", sa.String(50), nullable=False),
        sa.Column("issue_key", sa.String(50), nullable=False),
        sa.Column("risk", sa.String(50), nullable=True),
        sa.Column("status", sa.String(100), nullable=True),
        sa.Column("cab_approval_required", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("approver", sa.String(255), nullable=True),
        sa.Column("ingested_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_change_requests_id", "change_requests", ["id"], unique=False)
    op.create_index("ix_change_requests_change_id", "change_requests", ["change_id"], unique=True)
    op.create_index("ix_change_requests_issue_key", "change_requests", ["issue_key"], unique=False)

    # 5. incident_problem_links
    op.create_table(
        "incident_problem_links",
        sa.Column("id", sa.Integer(), nullable=False, autoincrement=True),
        sa.Column("link_id", sa.String(50), nullable=False),
        sa.Column("child_issue_key", sa.String(50), nullable=False),
        sa.Column("parent_incident_key", sa.String(50), nullable=False),
        sa.Column("relationship", sa.String(100), nullable=True),
        sa.Column("ingested_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_incident_problem_links_id", "incident_problem_links", ["id"], unique=False)
    op.create_index("ix_incident_problem_links_link_id", "incident_problem_links", ["link_id"], unique=True)
    op.create_index("ix_incident_problem_links_child_issue_key", "incident_problem_links", ["child_issue_key"], unique=False)
    op.create_index("ix_incident_problem_links_parent_incident_key", "incident_problem_links", ["parent_incident_key"], unique=False)

    # 6. sla_calendar
    op.create_table(
        "sla_calendar",
        sa.Column("id", sa.Integer(), nullable=False, autoincrement=True),
        sa.Column("region", sa.String(100), nullable=False),
        sa.Column("business_hours", sa.String(100), nullable=True),
        sa.Column("timezone", sa.String(100), nullable=True),
        sa.Column("holiday_dates", sa.Text(), nullable=True),
        sa.Column("ingested_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_sla_calendar_id", "sla_calendar", ["id"], unique=False)
    op.create_index("ix_sla_calendar_region", "sla_calendar", ["region"], unique=False)

    # 7. team_roster
    op.create_table(
        "team_roster",
        sa.Column("id", sa.Integer(), nullable=False, autoincrement=True),
        sa.Column("team", sa.String(100), nullable=False),
        sa.Column("member", sa.String(255), nullable=False),
        sa.Column("role", sa.String(100), nullable=True),
        sa.Column("on_call", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("assignment_group", sa.String(100), nullable=True),
        sa.Column("region", sa.String(100), nullable=True),
        sa.Column("ingested_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_team_roster_id", "team_roster", ["id"], unique=False)
    op.create_index("ix_team_roster_team", "team_roster", ["team"], unique=False)
    op.create_index("ix_team_roster_member", "team_roster", ["member"], unique=False)
    op.create_index("ix_team_roster_assignment_group", "team_roster", ["assignment_group"], unique=False)


def downgrade() -> None:
    op.drop_table("team_roster")
    op.drop_table("sla_calendar")
    op.drop_table("incident_problem_links")
    op.drop_table("change_requests")
    op.drop_table("csat_surveys")
    op.drop_table("ticket_comments")

    op.drop_index("ix_issues_linked_incident", table_name="issues")
    op.drop_column("issues", "x_confidence")
    op.drop_column("issues", "linked_incident")
    op.drop_column("issues", "first_response_time")
    op.drop_column("issues", "x_reopened")
    op.drop_column("issues", "x_escalation_risk")
    op.drop_column("issues", "x_channel")
