#!/usr/bin/env python3
"""
scripts/seed_hackathon_data.py
==============================
Reads the 5 official hackathon CSVs from /app/data/ and inserts all rows
into the corresponding PostgreSQL tables.

Also seeds workbench_items with:
  - ITSM-2013 (David Ng, VIP) flagged as pending_approval  ← primary demo item
  - ITSM-2014 (Uma Das)       flagged as pending_approval  ← secondary demo item

Run inside the backend container:
  docker exec autopilot-template-backend-1 python scripts/seed_hackathon_data.py

Or locally (needs DATABASE_URL in env):
  DATABASE_URL=postgresql://user:password@localhost:5432/app_db python scripts/seed_hackathon_data.py
"""

import csv
import os
import sys
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# ---------------------------------------------------------------------------
# Path setup — works both inside container (/app) and locally
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"

sys.path.insert(0, str(BASE_DIR))

from app.models.hackathon import AssetAccess, FieldDictionary, Issue, KnowledgeBase, UserDirectory
from app.models.workbench import WorkbenchItem

# ---------------------------------------------------------------------------
# Database connection
# ---------------------------------------------------------------------------
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    print("❌  DATABASE_URL not set. Exiting.")
    sys.exit(1)

engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def parse_bool(val: str) -> bool:
    return str(val).strip().lower() in ("true", "1", "yes")


def read_csv(filename: str) -> list[dict]:
    path = DATA_DIR / filename
    if not path.exists():
        print(f"⚠️  File not found: {path}")
        return []
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        return [row for row in reader]


def truncate_tables(session, table_names: list[str]):
    """Clear tables before re-seeding (idempotent)."""
    for name in table_names:
        session.execute(text(f'TRUNCATE TABLE "{name}" RESTART IDENTITY CASCADE'))
    session.commit()
    print(f"🗑️  Cleared: {', '.join(table_names)}")


# ---------------------------------------------------------------------------
# Seed functions
# ---------------------------------------------------------------------------

def seed_issues(session) -> int:
    rows = read_csv("Issues.csv")
    objects = []
    for r in rows:
        objects.append(Issue(
            issue_key=r.get("Issue key", "").strip(),
            issue_id=r.get("Issue id", "").strip() or None,
            issue_type=r.get("Issue Type", "").strip() or None,
            summary=r.get("Summary", "").strip(),
            description=r.get("Description", "").strip() or None,
            priority=r.get("Priority", "").strip() or None,
            status=r.get("Status", "").strip() or None,
            resolution=r.get("Resolution", "").strip() or None,
            assignee=r.get("Assignee", "").strip() or None,
            reporter=r.get("Reporter", "").strip() or None,
            created=r.get("Created", "").strip() or None,
            updated=r.get("Updated", "").strip() or None,
            due_date=r.get("Due date", "").strip() or None,
            project_key=r.get("Project key", "").strip() or None,
            components=r.get("Components", "").strip() or None,
            labels=r.get("Labels", "").strip() or None,
            request_type=r.get("Request Type", "").strip() or None,
            organizations=r.get("Organizations", "").strip() or None,
            time_to_resolution=r.get("customfield_10030 (Time to resolution)", "").strip() or None,
            assignment_group=r.get("customfield_10101 (Assignment group)", "").strip() or None,
        ))
    session.bulk_save_objects(objects)
    session.commit()
    return len(objects)


def seed_users_directory(session) -> int:
    rows = read_csv("Users_Directory.csv")
    objects = []
    for r in rows:
        objects.append(UserDirectory(
            account_id=r.get("account_id", "").strip(),
            display_name=r.get("display_name", "").strip(),
            email_address=r.get("email_address", "").strip() or None,
            department=r.get("department", "").strip() or None,
            x_vip=parse_bool(r.get("x_vip", "false")),
            location=r.get("location", "").strip() or None,
        ))
    session.bulk_save_objects(objects)
    session.commit()
    return len(objects)


def seed_assets_access(session) -> int:
    rows = read_csv("Assets_Access.csv")
    objects = []
    for r in rows:
        objects.append(AssetAccess(
            object_key=r.get("object_key", "").strip(),
            object_type=r.get("object_type", "").strip() or None,
            affected_user=r.get("affected_user", "").strip() or None,
            system=r.get("system", "").strip() or None,
            access_level=r.get("access_level", "").strip() or None,
            status=r.get("status", "").strip() or None,
        ))
    session.bulk_save_objects(objects)
    session.commit()
    return len(objects)


def seed_knowledge_base(session) -> int:
    rows = read_csv("Knowledge_Base.csv")
    objects = []
    for r in rows:
        article_id = r.get("article_id", "").strip()
        if not article_id:
            continue
        objects.append(KnowledgeBase(
            article_id=article_id,
            title=r.get("title", "").strip(),
            root_cause=r.get("root_cause", "").strip() or None,
            workaround=r.get("workaround", "").strip() or None,
            x_auto_safe=parse_bool(r.get("x_auto_safe", "false")),
        ))
    session.bulk_save_objects(objects)
    session.commit()
    return len(objects)


def seed_field_dictionary(session) -> int:
    rows = read_csv("Field_Dictionary.csv")
    objects = []
    for r in rows:
        sheet = r.get("Sheet", "").strip()
        if not sheet:
            continue
        objects.append(FieldDictionary(
            sheet=sheet,
            description=r.get("Description", "").strip() or None,
            data_class=r.get("Class", "").strip() or None,
        ))
    session.bulk_save_objects(objects)
    session.commit()
    return len(objects)


def seed_workbench_items(session) -> int:
    """
    Seed the HITL exception queue.

    ITSM-2013 — David Ng (VIP Executive)
      Issue: Cannot access board reporting dashboard (login loop)
      KB match: KB-103 — SSO loop on dashboard login / stale token cache
      Action: Clear token cache, re-issue SAML assertion
      Status: pending_approval  ← primary demo item for workbench

    ITSM-2014 — Uma Das
      Issue: Laptop running slow — Highest priority, At risk SLA
      Status: pending_approval  ← secondary demo item
    """
    items = [
        WorkbenchItem(
            ticket_key="ITSM-2013",
            summary="Cannot access board reporting dashboard",
            reporter_name="Faizal Das",
            reporter_email="faizal.das@company.com",
            vip_user=True,
            organization="Executive",
            priority="High",
            diagnosis=(
                "SSO login loop detected on board reporting dashboard. "
                "Stale token cache identified — SAML assertion expired. "
                "Matched KB-103: SSO loop on dashboard login."
            ),
            proposed_action=(
                "Clear David Ng's SSO token cache and re-issue SAML assertion. "
                "Estimated resolution time: 15 minutes. "
                "KB-103 marks this as auto-safe — but VIP flag requires human approval."
            ),
            kb_article_id="KB-103",
            status="pending_approval",
        ),
        WorkbenchItem(
            ticket_key="ITSM-2014",
            summary="Laptop running slow",
            reporter_name="Wei Goh",
            reporter_email="wei.goh@company.com",
            vip_user=False,
            organization="Finance",
            priority="Highest",
            diagnosis=(
                "Laptop performance degraded. Possible causes: high CPU from background processes, "
                "low disk space, or malware. Ticket has been waiting for support — SLA At Risk."
            ),
            proposed_action=(
                "Dispatch Field Support to run diagnostics. "
                "If disk < 10% free: archive user data. "
                "If malware detected: escalate to Security team."
            ),
            kb_article_id=None,
            status="pending_approval",
        ),
    ]
    session.bulk_save_objects(items)
    session.commit()
    return len(items)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("🌱  Starting hackathon data seed...\n")

    with Session() as session:
        # Clear all target tables first (idempotent re-run)
        truncate_tables(session, [
            "workbench_items",
            "field_dictionary",
            "knowledge_base",
            "assets_access",
            "users_directory",
            "issues",
        ])

        n = seed_issues(session)
        print(f"✅  issues             → {n} rows")

        n = seed_users_directory(session)
        print(f"✅  users_directory    → {n} rows")

        n = seed_assets_access(session)
        print(f"✅  assets_access      → {n} rows")

        n = seed_knowledge_base(session)
        print(f"✅  knowledge_base     → {n} rows")

        n = seed_field_dictionary(session)
        print(f"✅  field_dictionary   → {n} rows")

        n = seed_workbench_items(session)
        print(f"✅  workbench_items    → {n} rows (ITSM-2013 pending_approval)")

    print("\n🎉  Seed complete! ITSM-2013 is ready in the Workbench queue.")


if __name__ == "__main__":
    main()
