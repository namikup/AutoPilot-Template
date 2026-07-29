"""Add hackathon dataset tables and workbench_items

Revision ID: d4e5f6g7h8i9
Revises: c3d4e5f6g7h8
Create Date: 2026-07-30 02:59:00.000000

Creates:
  - issues             (Issues.csv mirror)
  - users_directory    (Users_Directory.csv mirror)
  - assets_access      (Assets_Access.csv mirror)
  - knowledge_base     (Knowledge_Base.csv mirror)
  - field_dictionary   (Field_Dictionary.csv mirror)
  - workbench_items    (HITL exception queue)
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d4e5f6g7h8i9"
down_revision: Union[str, None] = "c3d4e5f6g7h8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # =========================================================================
    # issues
    # =========================================================================
    op.create_table(
        "issues",
        sa.Column("id", sa.Integer(), nullable=False, autoincrement=True),
        sa.Column("issue_key", sa.String(50), nullable=False),
        sa.Column("issue_id", sa.String(50), nullable=True),
        sa.Column("issue_type", sa.String(100), nullable=True),
        sa.Column("summary", sa.String(500), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("priority", sa.String(50), nullable=True),
        sa.Column("status", sa.String(100), nullable=True),
        sa.Column("resolution", sa.String(100), nullable=True),
        sa.Column("assignee", sa.String(255), nullable=True),
        sa.Column("reporter", sa.String(255), nullable=True),
        sa.Column("created", sa.String(50), nullable=True),
        sa.Column("updated", sa.String(50), nullable=True),
        sa.Column("due_date", sa.String(50), nullable=True),
        sa.Column("project_key", sa.String(50), nullable=True),
        sa.Column("components", sa.String(255), nullable=True),
        sa.Column("labels", sa.String(500), nullable=True),
        sa.Column("request_type", sa.String(255), nullable=True),
        sa.Column("organizations", sa.String(255), nullable=True),
        sa.Column("time_to_resolution", sa.String(100), nullable=True),
        sa.Column("assignment_group", sa.String(100), nullable=True),
        sa.Column("ingested_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_issues_id", "issues", ["id"], unique=False)
    op.create_index("ix_issues_issue_key", "issues", ["issue_key"], unique=True)
    op.create_index("ix_issues_status", "issues", ["status"], unique=False)
    op.create_index("ix_issues_priority", "issues", ["priority"], unique=False)
    op.create_index("ix_issues_reporter", "issues", ["reporter"], unique=False)
    op.create_index("ix_issues_organizations", "issues", ["organizations"], unique=False)

    # =========================================================================
    # users_directory
    # =========================================================================
    op.create_table(
        "users_directory",
        sa.Column("id", sa.Integer(), nullable=False, autoincrement=True),
        sa.Column("account_id", sa.String(100), nullable=False),
        sa.Column("display_name", sa.String(255), nullable=False),
        sa.Column("email_address", sa.String(255), nullable=True),
        sa.Column("department", sa.String(100), nullable=True),
        sa.Column("x_vip", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("location", sa.String(100), nullable=True),
        sa.Column("ingested_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_users_directory_id", "users_directory", ["id"], unique=False)
    op.create_index("ix_users_directory_account_id", "users_directory", ["account_id"], unique=True)
    op.create_index("ix_users_directory_display_name", "users_directory", ["display_name"], unique=False)
    op.create_index("ix_users_directory_email_address", "users_directory", ["email_address"], unique=False)
    op.create_index("ix_users_directory_department", "users_directory", ["department"], unique=False)
    op.create_index("ix_users_directory_x_vip", "users_directory", ["x_vip"], unique=False)

    # =========================================================================
    # assets_access
    # =========================================================================
    op.create_table(
        "assets_access",
        sa.Column("id", sa.Integer(), nullable=False, autoincrement=True),
        sa.Column("object_key", sa.String(50), nullable=False),
        sa.Column("object_type", sa.String(100), nullable=True),
        sa.Column("affected_user", sa.String(255), nullable=True),
        sa.Column("system", sa.String(100), nullable=True),
        sa.Column("access_level", sa.String(50), nullable=True),
        sa.Column("status", sa.String(50), nullable=True),
        sa.Column("ingested_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_assets_access_id", "assets_access", ["id"], unique=False)
    op.create_index("ix_assets_access_object_key", "assets_access", ["object_key"], unique=False)
    op.create_index("ix_assets_access_affected_user", "assets_access", ["affected_user"], unique=False)
    op.create_index("ix_assets_access_system", "assets_access", ["system"], unique=False)
    op.create_index("ix_assets_access_status", "assets_access", ["status"], unique=False)

    # =========================================================================
    # knowledge_base
    # =========================================================================
    op.create_table(
        "knowledge_base",
        sa.Column("id", sa.Integer(), nullable=False, autoincrement=True),
        sa.Column("article_id", sa.String(50), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("root_cause", sa.Text(), nullable=True),
        sa.Column("workaround", sa.Text(), nullable=True),
        sa.Column("x_auto_safe", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("ingested_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_knowledge_base_id", "knowledge_base", ["id"], unique=False)
    op.create_index("ix_knowledge_base_article_id", "knowledge_base", ["article_id"], unique=True)
    op.create_index("ix_knowledge_base_x_auto_safe", "knowledge_base", ["x_auto_safe"], unique=False)

    # =========================================================================
    # field_dictionary
    # =========================================================================
    op.create_table(
        "field_dictionary",
        sa.Column("id", sa.Integer(), nullable=False, autoincrement=True),
        sa.Column("sheet", sa.String(100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("data_class", sa.String(50), nullable=True),
        sa.Column("ingested_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_field_dictionary_id", "field_dictionary", ["id"], unique=False)
    op.create_index("ix_field_dictionary_sheet", "field_dictionary", ["sheet"], unique=False)

    # =========================================================================
    # workbench_items
    # =========================================================================
    op.create_table(
        "workbench_items",
        sa.Column("id", sa.Integer(), nullable=False, autoincrement=True),
        sa.Column("ticket_key", sa.String(50), nullable=False),
        sa.Column("summary", sa.String(500), nullable=False),
        sa.Column("reporter_email", sa.String(255), nullable=True),
        sa.Column("reporter_name", sa.String(255), nullable=True),
        sa.Column("vip_user", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("organization", sa.String(255), nullable=True),
        sa.Column("priority", sa.String(50), nullable=True),
        sa.Column("diagnosis", sa.Text(), nullable=True),
        sa.Column("proposed_action", sa.Text(), nullable=True),
        sa.Column("kb_article_id", sa.String(50), nullable=True),
        sa.Column("status", sa.String(50), nullable=False, server_default="pending_approval"),
        sa.Column("reviewed_by", sa.String(255), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("review_note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_workbench_items_id", "workbench_items", ["id"], unique=False)
    op.create_index("ix_workbench_items_ticket_key", "workbench_items", ["ticket_key"], unique=False)
    op.create_index("ix_workbench_items_status", "workbench_items", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_workbench_items_status", table_name="workbench_items")
    op.drop_index("ix_workbench_items_ticket_key", table_name="workbench_items")
    op.drop_index("ix_workbench_items_id", table_name="workbench_items")
    op.drop_table("workbench_items")

    op.drop_index("ix_field_dictionary_sheet", table_name="field_dictionary")
    op.drop_index("ix_field_dictionary_id", table_name="field_dictionary")
    op.drop_table("field_dictionary")

    op.drop_index("ix_knowledge_base_x_auto_safe", table_name="knowledge_base")
    op.drop_index("ix_knowledge_base_article_id", table_name="knowledge_base")
    op.drop_index("ix_knowledge_base_id", table_name="knowledge_base")
    op.drop_table("knowledge_base")

    op.drop_index("ix_assets_access_status", table_name="assets_access")
    op.drop_index("ix_assets_access_system", table_name="assets_access")
    op.drop_index("ix_assets_access_affected_user", table_name="assets_access")
    op.drop_index("ix_assets_access_object_key", table_name="assets_access")
    op.drop_index("ix_assets_access_id", table_name="assets_access")
    op.drop_table("assets_access")

    op.drop_index("ix_users_directory_x_vip", table_name="users_directory")
    op.drop_index("ix_users_directory_department", table_name="users_directory")
    op.drop_index("ix_users_directory_email_address", table_name="users_directory")
    op.drop_index("ix_users_directory_display_name", table_name="users_directory")
    op.drop_index("ix_users_directory_account_id", table_name="users_directory")
    op.drop_index("ix_users_directory_id", table_name="users_directory")
    op.drop_table("users_directory")

    op.drop_index("ix_issues_organizations", table_name="issues")
    op.drop_index("ix_issues_reporter", table_name="issues")
    op.drop_index("ix_issues_priority", table_name="issues")
    op.drop_index("ix_issues_status", table_name="issues")
    op.drop_index("ix_issues_issue_key", table_name="issues")
    op.drop_index("ix_issues_id", table_name="issues")
    op.drop_table("issues")
