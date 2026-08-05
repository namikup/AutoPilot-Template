# app/models/hackathon.py
"""
Hackathon Dataset Models — mirrors the 11 official CSV datasets (Round 2 Enterprise Export).

Tables:
  issues                  ← Issues.csv                  (ITSM ticket export + Round 2 extensions)
  users_directory         ← Users_Directory.csv         (reporter/user profiles + VIP flag)
  assets_access           ← Assets_Access.csv           (JSM asset/access objects)
  knowledge_base          ← Knowledge_Base.csv          (KB articles with auto-safe flag)
  field_dictionary        ← Field_Dictionary.csv        (data dictionary / sheet metadata)
  ticket_comments         ← Ticket_Comments.csv         (threaded comments per ticket)
  csat_surveys            ← CSAT_Surveys.csv            (customer satisfaction responses)
  change_requests         ← Change_Requests.csv         (CAB change approvals)
  incident_problem_links  ← Incident_Problem_Links.csv  (correlated incident/problem hierarchy)
  sla_calendar            ← SLA_Calendar.csv            (regional business hours & holidays)
  team_roster             ← Team_Roster.csv             (team members, on-call status, regions)
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, Column, DateTime, Float, Integer, String, Text, func

from ..core.database import Base


class Issue(Base):
    """
    Issues.csv — full JSM issue export (Round 2).
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

    # Dates
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

    # Round 2 extension fields
    x_channel = Column(String(50), nullable=True)              # email/chat/portal
    x_escalation_risk = Column(String(50), nullable=True)      # Low/High/Critical
    x_reopened = Column(Boolean, nullable=False, default=False)
    first_response_time = Column(String(50), nullable=True)
    linked_incident = Column(String(50), nullable=True, index=True)
    x_confidence = Column(Float, nullable=True)

    # Row ingestion timestamp
    ingested_at = Column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self):
        return f"<Issue {self.issue_key}: {self.summary[:40]}>"


class UserDirectory(Base):
    """
    Users_Directory.csv — reporter/user profiles with VIP flag.
    """

    __tablename__ = "users_directory"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)

    account_id = Column(String(100), unique=True, nullable=False, index=True)
    display_name = Column(String(255), nullable=False, index=True)
    email_address = Column(String(255), nullable=True, index=True)
    department = Column(String(100), nullable=True, index=True)
    x_vip = Column(Boolean, nullable=False, default=False)
    location = Column(String(100), nullable=True)

    ingested_at = Column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self):
        return f"<UserDirectory {self.display_name} vip={self.x_vip}>"


class AssetAccess(Base):
    """
    Assets_Access.csv — JSM Assets/Insight access objects.
    """

    __tablename__ = "assets_access"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)

    object_key = Column(String(50), nullable=False, index=True)
    object_type = Column(String(100), nullable=True)
    affected_user = Column(String(255), nullable=True, index=True)
    system = Column(String(100), nullable=True, index=True)
    access_level = Column(String(50), nullable=True)
    status = Column(String(50), nullable=True, index=True)

    ingested_at = Column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self):
        return f"<AssetAccess {self.object_key} {self.affected_user} → {self.system}>"


class KnowledgeBase(Base):
    """
    Knowledge_Base.csv — KB articles with auto-remediation safety flag.
    """

    __tablename__ = "knowledge_base"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)

    article_id = Column(String(50), unique=True, nullable=False, index=True)
    title = Column(String(500), nullable=False)
    root_cause = Column(Text, nullable=True)
    workaround = Column(Text, nullable=True)
    x_auto_safe = Column(Boolean, nullable=False, default=False)

    ingested_at = Column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self):
        return f"<KnowledgeBase {self.article_id}: {self.title[:40]}>"


class FieldDictionary(Base):
    """
    Field_Dictionary.csv — data dictionary / sheet metadata.
    """

    __tablename__ = "field_dictionary"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)

    sheet = Column(String(100), nullable=False, index=True)
    description = Column(Text, nullable=True)
    data_class = Column(String(50), nullable=True)

    ingested_at = Column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self):
        return f"<FieldDictionary {self.sheet} ({self.data_class})>"


class TicketComment(Base):
    """
    Ticket_Comments.csv — conversation thread per ticket.
    """

    __tablename__ = "ticket_comments"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)

    comment_id = Column(String(50), unique=True, nullable=False, index=True) # CMT-00001
    issue_key = Column(String(50), nullable=False, index=True)               # ITSM-2180
    author = Column(String(255), nullable=True)
    created = Column(String(50), nullable=True)
    body = Column(Text, nullable=True)
    is_internal = Column(Boolean, nullable=False, default=False)

    ingested_at = Column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self):
        return f"<TicketComment {self.comment_id} on {self.issue_key}>"


class CSATSurvey(Base):
    """
    CSAT_Surveys.csv — satisfaction survey per resolved ticket.
    """

    __tablename__ = "csat_surveys"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)

    survey_id = Column(String(50), unique=True, nullable=False, index=True) # CSAT-0001
    issue_key = Column(String(50), nullable=False, index=True)              # ITSM-2018
    score = Column(Integer, nullable=True)                                   # 1 - 5
    comment = Column(Text, nullable=True)
    submitted_at = Column(String(50), nullable=True)

    ingested_at = Column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self):
        return f"<CSATSurvey {self.survey_id} score={self.score}>"


class ChangeRequest(Base):
    """
    Change_Requests.csv — CAB change approvals.
    """

    __tablename__ = "change_requests"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)

    change_id = Column(String(50), unique=True, nullable=False, index=True) # CHG-0001
    issue_key = Column(String(50), nullable=False, index=True)              # ITSM-2180
    risk = Column(String(50), nullable=True)                                 # High / Medium / Low
    status = Column(String(100), nullable=True)                              # Pending CAB Approval / etc.
    cab_approval_required = Column(Boolean, nullable=False, default=True)
    approver = Column(String(255), nullable=True)

    ingested_at = Column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self):
        return f"<ChangeRequest {self.change_id} for {self.issue_key}>"


class IncidentProblemLink(Base):
    """
    Incident_Problem_Links.csv — links child tickets to a parent incident/problem.
    """

    __tablename__ = "incident_problem_links"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)

    link_id = Column(String(50), unique=True, nullable=False, index=True)       # LNK-0001
    child_issue_key = Column(String(50), nullable=False, index=True)            # ITSM-2181
    parent_incident_key = Column(String(50), nullable=False, index=True)        # ITSM-2180
    relationship = Column(String(100), nullable=True)                           # is caused by / relates to / etc.

    ingested_at = Column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self):
        return f"<IncidentProblemLink {self.child_issue_key} → {self.parent_incident_key}>"


class SLACalendar(Base):
    """
    SLA_Calendar.csv — business hours, timezone, and holiday dates per region.
    """

    __tablename__ = "sla_calendar"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)

    region = Column(String(100), nullable=False, index=True) # Singapore / KL-HQ / Penang / Remote
    business_hours = Column(String(100), nullable=True)
    timezone = Column(String(100), nullable=True)
    holiday_dates = Column(Text, nullable=True)

    ingested_at = Column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self):
        return f"<SLACalendar {self.region}>"


class TeamRoster(Base):
    """
    Team_Roster.csv — teams, members, on_call flag, assignment group, region.
    """

    __tablename__ = "team_roster"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)

    team = Column(String(100), nullable=False, index=True)
    member = Column(String(255), nullable=False, index=True)
    role = Column(String(100), nullable=True)
    on_call = Column(Boolean, nullable=False, default=False)
    assignment_group = Column(String(100), nullable=True, index=True)
    region = Column(String(100), nullable=True)

    ingested_at = Column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self):
        return f"<TeamRoster {self.member} ({self.team})>"
