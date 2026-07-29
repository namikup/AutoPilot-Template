# app/models/hackathon.py
"""
Hackathon Dataset Models — mirrors the 5 official CSV datasets.

Tables:
  issues            ← Issues.csv           (ITSM ticket export)
  users_directory   ← Users_Directory.csv  (reporter/user profiles + VIP flag)
  assets_access     ← Assets_Access.csv    (JSM asset/access objects)
  knowledge_base    ← Knowledge_Base.csv   (KB articles with auto-safe flag)
  field_dictionary  ← Field_Dictionary.csv (data dictionary / sheet metadata)
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text, func

from ..core.database import Base


class Issue(Base):
    """
    Issues.csv — full JSM issue export.

    Columns (exact CSV names preserved as snake_case):
      issue_key, issue_id, issue_type, summary, description, priority,
      status, resolution, assignee, reporter, created, updated, due_date,
      project_key, components, labels, request_type, organizations,
      time_to_resolution (customfield_10030), assignment_group (customfield_10101)
    """

    __tablename__ = "issues"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)

    # Core identifiers
    issue_key = Column(String(50), unique=True, nullable=False, index=True)   # e.g. ITSM-2013
    issue_id = Column(String(50), nullable=True)                               # e.g. 310013

    # Classification
    issue_type = Column(String(100), nullable=True)    # Incident / Service Request
    summary = Column(String(500), nullable=False)
    description = Column(Text, nullable=True)
    priority = Column(String(50), nullable=True, index=True)   # Low/Medium/High/Highest
    status = Column(String(100), nullable=True, index=True)    # Open/In Progress/Waiting…
    resolution = Column(String(100), nullable=True)            # Done / blank

    # People
    assignee = Column(String(255), nullable=True)
    reporter = Column(String(255), nullable=True, index=True)

    # Dates (stored as strings to match raw CSV format; parse on read)
    created = Column(String(50), nullable=True)
    updated = Column(String(50), nullable=True)
    due_date = Column(String(50), nullable=True)

    # Project metadata
    project_key = Column(String(50), nullable=True)
    components = Column(String(255), nullable=True)
    labels = Column(String(500), nullable=True)

    # JSM-specific
    request_type = Column(String(255), nullable=True)
    organizations = Column(String(255), nullable=True, index=True)

    # Custom fields
    time_to_resolution = Column(String(100), nullable=True)   # customfield_10030: SLA status
    assignment_group = Column(String(100), nullable=True)     # customfield_10101

    # Row ingestion timestamp
    ingested_at = Column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self):
        return f"<Issue {self.issue_key}: {self.summary[:40]}>"


class UserDirectory(Base):
    """
    Users_Directory.csv — reporter/user profiles with VIP flag.

    Columns: account_id, display_name, email_address, department, x_vip, location
    """

    __tablename__ = "users_directory"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)

    account_id = Column(String(100), unique=True, nullable=False, index=True)
    display_name = Column(String(255), nullable=False, index=True)
    email_address = Column(String(255), nullable=True, index=True)
    department = Column(String(100), nullable=True, index=True)
    x_vip = Column(Boolean, nullable=False, default=False)   # True → VIP user
    location = Column(String(100), nullable=True)

    ingested_at = Column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self):
        return f"<UserDirectory {self.display_name} vip={self.x_vip}>"


class AssetAccess(Base):
    """
    Assets_Access.csv — JSM Assets/Insight access objects.

    Columns: object_key, object_type, affected_user, system, access_level, status
    Status values: Active / Pending / Revoked
    """

    __tablename__ = "assets_access"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)

    object_key = Column(String(50), nullable=False, index=True)   # e.g. ITSM-1000
    object_type = Column(String(100), nullable=True)              # e.g. Access Grant
    affected_user = Column(String(255), nullable=True, index=True)
    system = Column(String(100), nullable=True, index=True)       # CRM / FileShare / Email / ERP
    access_level = Column(String(50), nullable=True)              # read / write / admin
    status = Column(String(50), nullable=True, index=True)        # Active / Pending / Revoked

    ingested_at = Column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self):
        return f"<AssetAccess {self.object_key} {self.affected_user} → {self.system}>"


class KnowledgeBase(Base):
    """
    Knowledge_Base.csv — KB articles with auto-remediation safety flag.

    Columns: article_id, title, root_cause, workaround, x_auto_safe
    x_auto_safe = true → agent can apply fix automatically without human review
    """

    __tablename__ = "knowledge_base"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)

    article_id = Column(String(50), unique=True, nullable=False, index=True)  # e.g. KB-103
    title = Column(String(500), nullable=False)
    root_cause = Column(Text, nullable=True)
    workaround = Column(Text, nullable=True)
    x_auto_safe = Column(Boolean, nullable=False, default=False)  # True → auto-remediation OK

    ingested_at = Column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self):
        return f"<KnowledgeBase {self.article_id}: {self.title[:40]}>"


class FieldDictionary(Base):
    """
    Field_Dictionary.csv — data dictionary / sheet metadata.

    Columns: sheet, description, class
    'class' is a reserved word in Python; stored as data_class.
    """

    __tablename__ = "field_dictionary"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)

    sheet = Column(String(100), nullable=False, index=True)         # e.g. Issues
    description = Column(Text, nullable=True)
    data_class = Column(String(50), nullable=True)                  # transactional / master / note

    ingested_at = Column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self):
        return f"<FieldDictionary {self.sheet} ({self.data_class})>"
