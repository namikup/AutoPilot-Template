#!/usr/bin/env python3
"""
scripts/seed_policies.py
=========================
Seeds the `policies` table with the default AI governance policies.

Idempotent: uses a Postgres UPSERT (INSERT ... ON CONFLICT (id) DO UPDATE),
so re-running this script refreshes the 5 policies in place instead of
creating duplicates or failing on the primary key.

Run inside the backend container:
  docker exec autopilot-template-backend-1 python scripts/seed_policies.py

Or locally (needs DATABASE_URL in env):
  DATABASE_URL=postgresql://user:password@localhost:5432/app_db python scripts/seed_policies.py
"""

import os
import sys
from pathlib import Path

from sqlalchemy import create_engine, func
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import sessionmaker

# ---------------------------------------------------------------------------
# Path setup — works both inside container (/app) and locally
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from app.models.policy import Policy

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
# Policy definitions
# ---------------------------------------------------------------------------
POLICIES = [
    {
        "id": "DATA_COMPLETENESS",
        "name": "Data completeness",
        "description": "Blocks action when required ticket fields are missing. The agent must never infer a missing value.",
        "category": "safety",
        "enabled": True,
        "priority": 1,
        "params": {
            "required_fields": ["x_channel", "x_confidence", "Components", "Reporter"],
            "on_missing": "ESCALATE",
            "allow_inference": False,
        },
    },
    {
        "id": "CHANGE_APPROVAL_GATE",
        "name": "Change approval gate",
        "description": "High-risk changes and anything flagged for CAB must be approved by a human before touching production.",
        "category": "change_control",
        "enabled": True,
        "priority": 5,
        "params": {
            "block_risk_levels": ["High"],
            "require_cab_when_flagged": True,
            "auto_approve_low_risk": False,
            "rollback_requires_approval": True,
        },
    },
    {
        "id": "AUTO_REMEDIATION_SAFETY",
        "name": "Auto-remediation safety",
        "description": "Only low-risk fixes with an auto-safe KB article and high diagnosis confidence may execute without a human.",
        "category": "safety",
        "enabled": True,
        "priority": 10,
        "params": {
            "min_confidence": 0.80,
            "require_kb_auto_safe": True,
            "blocked_components": ["Payroll", "SSO"],
            "max_priority_for_auto": "High",
            "block_if_reopened": True,
        },
    },
    {
        "id": "SLA_VIP_ESCALATION",
        "name": "SLA and VIP escalation",
        "description": "Escalates tickets close to breaching their business-hours SLA. VIP requesters get tighter targets and are handled outside business hours.",
        "category": "sla",
        "enabled": True,
        "priority": 20,
        "params": {
            "escalate_below_remaining_pct": 25,
            "priority_targets_hours": {"Highest": 4, "High": 8, "Medium": 24, "Low": 48},
            "vip_multiplier": 2.0,
            "vip_ignores_business_hours": True,
            "breached_goes_straight_to_lead": True,
        },
    },
    {
        "id": "STALL_DETECTION",
        "name": "Stalled ticket detection",
        "description": "Flags tickets with no meaningful update beyond the threshold for their priority. Reopened tickets get a tighter threshold.",
        "category": "monitoring",
        "enabled": True,
        "priority": 30,
        "params": {
            "stall_hours_by_priority": {"Highest": 4, "High": 12, "Medium": 24, "Low": 48},
            "count_business_hours_only": True,
            "waiting_for_customer_pauses_clock": True,
            "reopened_reduces_threshold_pct": 50,
        },
    },
]


# ---------------------------------------------------------------------------
# Seed function
# ---------------------------------------------------------------------------

def seed_policies(session) -> int:
    """Upsert each policy on id — safe to re-run without creating duplicates."""
    for policy in POLICIES:
        stmt = pg_insert(Policy).values(
            id=policy["id"],
            name=policy["name"],
            description=policy["description"],
            category=policy["category"],
            enabled=policy["enabled"],
            priority=policy["priority"],
            params=policy["params"],
            version=1,
            updated_by="system",
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=["id"],
            set_={
                "name": stmt.excluded.name,
                "description": stmt.excluded.description,
                "category": stmt.excluded.category,
                "enabled": stmt.excluded.enabled,
                "priority": stmt.excluded.priority,
                "params": stmt.excluded.params,
                "version": stmt.excluded.version,
                "updated_by": stmt.excluded.updated_by,
                "updated_at": func.now(),
            },
        )
        session.execute(stmt)
    session.commit()
    return len(POLICIES)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("🌱  Seeding AI policies...\n")

    with Session() as session:
        n = seed_policies(session)
        print(f"✅  policies           → {n} rows upserted")

    print("\n🎉  Policy seed complete!")


if __name__ == "__main__":
    main()
