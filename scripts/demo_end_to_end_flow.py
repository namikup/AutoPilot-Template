#!/usr/bin/env python3
"""
Full End-to-End Demonstration Script for Autopilot Asia Hackathon Round 2.

Complete 6-Step Lifecycle:
  1. Ticket Arrives          → Identify stalled/VIP ticket (ITSM-2008).
  2. Agent Evaluates Policy  → POST /api/policies/evaluate (evaluates active policy rules).
  3. Exception Hits Workbench→ Verdict ESCALATE auto-creates WorkbenchItem #id.
  4. Human Approves          → POST /api/workbench/{id}/approve (human approval cleared).
  5. Ticket Resolution & CSAT→ Agent resolves ticket and logs CSAT survey feedback.
  6. Command Center Check    → Real-time AI Manager verification & operational metrics.
"""

import os
import sys
import time
import httpx
from sqlalchemy import create_engine, text

API_BASE = "http://localhost:8001/api"
DB_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://user:password@localhost:5432/app_db"
)

def print_step(num: int, title: str):
    print(f"\n================================================================================")
    print(f"  STEP {num}: {title.upper()}")
    print(f"================================================================================")

def main():
    print("🚀 STARTING AUTOPILOT ROUND 2 END-TO-END DEMONSTRATION FLOW...\n")

    # Connect to DB for direct resolution & CSAT logging
    try:
        engine = create_engine(DB_URL)
    except Exception as e:
        engine = None
        print(f"⚠️ Direct DB connection note: {e}")

    # -------------------------------------------------------------------------
    # STEP 1: Ticket Arrives
    # -------------------------------------------------------------------------
    print_step(1, "Ticket Arrives (Stalled / VIP Ticket Identification)")
    ticket_key = "ITSM-2008"
    run_id = f"demo-run-{int(time.time())}"
    print(f"📌 Ticket Arrived:  {ticket_key}")
    print(f"📌 Execution Run ID:{run_id}")
    print(f"📌 Summary:         MFA device lost for Executive VIP user Chloe Fernandez")
    print(f"📌 Initial Status:   Open | Priority: Highest | SLA Remaining: 15.0%")

    # Reset ITSM-2008 to Open first to make demo repeatable
    if engine:
        with engine.connect() as conn:
            conn.execute(
                text("UPDATE issues SET status = 'Open' WHERE issue_key = :key"),
                {"key": ticket_key}
            )
            conn.commit()

    # -------------------------------------------------------------------------
    # STEP 2: Agent Evaluates Policy
    # -------------------------------------------------------------------------
    print_step(2, "Agent Evaluates Policy (POST /api/policies/evaluate)")
    policy_payload = {
        "run_id": run_id,
        "issue_key": ticket_key,
        "priority": "Highest",
        "is_vip": True,
        "confidence": 0.95,
        "component": "Authentication",
        "kb_article": "KB-101",
        "kb_auto_safe": True,
        "sla_remaining_pct": 15.0,
        "change_required": False,
        "reporter": "Chloe Fernandez",
        "x_channel": "portal",
        "auto_route_workbench": True,
    }

    print("Sending ticket context to Policy Rules Engine...")
    t0 = time.time()
    try:
        res = httpx.post(f"{API_BASE}/policies/evaluate", json=policy_payload, timeout=10.0)
        print(f"Policy Engine Response Time: {time.time()-t0:.3f}s | HTTP Status: {res.status_code}")
        eval_data = res.json()
        print(f"\n⚖️  OVERALL VERDICT: {eval_data.get('verdict')}")
        print(f"📝 VERDICT REASON:  {eval_data.get('reason')}")
        wb_item_id = eval_data.get("workbench_item_id")
        print(f"🔔 AUTO-CREATED WORKBENCH ITEM ID: {wb_item_id}")

        print("\nEvaluated Rules Audit Log:")
        for ev in eval_data.get("evaluations", []):
            print(f"  - Policy: {ev.get('policy_id'):<25} | Verdict: {ev.get('verdict'):<8} | Reason: {ev.get('reason')}")
    except Exception as e:
        print(f"❌ Error evaluating policies: {e}")
        sys.exit(1)

    # -------------------------------------------------------------------------
    # STEP 3: Exception Hits Workbench
    # -------------------------------------------------------------------------
    print_step(3, f"Exception Hits Workbench Queue (Item #{wb_item_id})")
    try:
        res = httpx.get(f"{API_BASE}/workbench/pending", timeout=10.0)
        pending_items = res.json()
        target_item = next((i for i in pending_items if str(i.get("id")) == str(wb_item_id)), None)
        if target_item:
            print(f"✅ Verified Exception Item #{wb_item_id} in Workbench Queue:")
            print(f"   - Ticket Key:  {target_item.get('ticket_key')}")
            print(f"   - Priority:    {target_item.get('priority')}")
            print(f"   - Status:      {target_item.get('status')}")
            print(f"   - Diagnosis:   {target_item.get('diagnosis')[:100]}...")
            print(f"   - Recommendation: {target_item.get('proposed_action')}")
        else:
            print(f"ℹ️ Item #{wb_item_id} created and queued.")
    except Exception as e:
        print(f"⚠️ Note fetching pending items: {e}")

    # -------------------------------------------------------------------------
    # STEP 4: Human Approves
    # -------------------------------------------------------------------------
    print_step(4, f"Human Approves Workbench Item (#{wb_item_id})")
    print(f"Human Operator reviewing exception item #{wb_item_id}...")
    review_payload = {
        "note": "Approved MFA device reset after executive VIP identity verification.",
        "reviewed_by": "Senior IT Admin",
    }

    t0 = time.time()
    try:
        res = httpx.post(f"{API_BASE}/workbench/{wb_item_id}/approve", json=review_payload, timeout=10.0)
        print(f"Approval Submission Latency: {time.time()-t0:.3f}s | HTTP Status: {res.status_code}")
        rev_data = res.json()
        print(f"✅ WORKBENCH ITEM STATUS: {rev_data.get('status').upper()}")
        print(f"📝 REVIEWER NOTE:        {rev_data.get('review_note')}")
        print(f"👤 REVIEWED BY:          {rev_data.get('reviewed_by')}")
    except Exception as e:
        print(f"❌ Error submitting workbench review: {e}")
        sys.exit(1)

    # -------------------------------------------------------------------------
    # STEP 5: Agent Resolves Ticket & CSAT Survey Recorded
    # -------------------------------------------------------------------------
    print_step(5, f"Agent Resolves Ticket ({ticket_key}) & CSAT Survey Recorded")
    import subprocess
    sql_cmd = f"""
        UPDATE issues SET status = 'Resolved', resolution = 'Done', updated = NOW()::text WHERE issue_key = '{ticket_key}';
        INSERT INTO csat_surveys (survey_id, issue_key, score, comment, submitted_at)
        VALUES ('CSAT-DEMO-{int(time.time())}', '{ticket_key}', 5, 'Fast VIP support and MFA reset approval!', NOW()::text)
        ON CONFLICT (survey_id) DO NOTHING;
    """
    try:
        res = subprocess.run([
            "docker", "exec", "autopilot-template-postgres-1",
            "psql", "-U", "user", "-d", "app_db", "-c", sql_cmd
        ], capture_output=True, text=True)
        if res.returncode == 0:
            print(f"✅ Ticket {ticket_key} status updated to: RESOLVED")
            print(f"⭐ Recorded CSAT Survey Response: 5/5 ('Fast VIP support and MFA reset approval!')")
        else:
            print(f"⚠️ SQL update output: {res.stderr}")
    except Exception as e:
        print(f"⚠️ DB Update Note: {e}")

    # -------------------------------------------------------------------------
    # STEP 6: Command Center Check (AI Manager Verification)
    # -------------------------------------------------------------------------
    print_step(6, "Command Center Check (AI Manager Verification)")
    ai_queries = [
        f"Tell me about {ticket_key}",
        "Any pending approvals?",
        "CSAT score?",
        "Give me a summary",
    ]

    for q in ai_queries:
        print(f"\n💬 USER QUESTION: {q!r}")
        t0 = time.time()
        res = httpx.post(f"{API_BASE}/ai/chat", json={"message": q}, timeout=10.0)
        print(f"   AI Manager Latency: {time.time()-t0:.3f}s | HTTP Status: {res.status_code}")
        ans = res.json().get("response", "")
        print(f"   🤖 AI RESPONSE:\n{ans}\n")

    print("================================================================================")
    print("🎉 FULL 6-STEP END-TO-END DEMONSTRATION FLOW COMPLETED SUCCESSFULLY!")
    print("================================================================================\n")


if __name__ == "__main__":
    main()
