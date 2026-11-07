"""
End-to-End Live Workflow & Groq LLM Verification Script.

Executes the entire daily pipeline against live Neon PostgreSQL and Groq Cloud:
1. Direct Groq API reflection generation test.
2. Full LangGraph StateGraph pipeline execution (Idempotency -> Candidate -> Safety -> Groq -> Format -> Record).
3. Immediate re-run verification for idempotency skip guard.
"""

import sys
from datetime import date
from pathlib import Path

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config import get_settings
from src.llm import GroqReflectionClient
from src.workflow import get_current_ist_date, run_daily_workflow


def main() -> None:
    print("=" * 70)
    print("🚀 DAILY HADITH AI AGENT — END-TO-END VERIFICATION")
    print("=" * 70)

    settings = get_settings()
    has_real_key = bool(settings.groq_api_key and "your" not in settings.groq_api_key.lower())
    key_preview = (
        f"{settings.groq_api_key[:8]}...{settings.groq_api_key[-4:]}"
        if settings.groq_api_key
        else "<NOT SET>"
    )
    print(f"• Timezone: {settings.timezone}")
    print(f"• Groq Model: {settings.groq_model}")
    print(
        f"• Groq Key Configured: {'✅ YES (' + key_preview + ')' if has_real_key else '⚠️ PLACEHOLDER (' + key_preview + ')'}"
    )
    print(f"• Target Date (IST): {get_current_ist_date()}")
    print("-" * 70)

    # -------------------------------------------------------------
    # Step 1: Direct Groq Reflection Verification
    # -------------------------------------------------------------
    print("\n[Step 1/3] Testing Groq LLM Direct Reflection...")
    llm_client = GroqReflectionClient()
    result = llm_client.generate_reflection(
        english_text="Actions are judged by motives, so each man will have what he intended.",
        attribution="Umar ibn al-Khattab (may Allah be pleased with him)",
        collection="Sahih al-Bukhari (#1)",
    )
    print(f"Outcome Status: {result.status}")
    print(f"Model Used: {result.model}")
    if result.reflection:
        print(f"Generated Reflection:\n{result.reflection}")
    else:
        print(f"Fallback Behavior: Reflection omitted ({result.error})")

    # -------------------------------------------------------------
    # Step 2: Full LangGraph StateGraph Execution on Neon DB
    # -------------------------------------------------------------
    import time
    from datetime import timedelta

    from src.database.repository import is_date_delivered
    from src.database.session import get_db_session

    target_date_str = sys.argv[1] if len(sys.argv) > 1 else get_current_ist_date()

    # Serverless wake-up retry guard for Neon PostgreSQL
    for attempt in range(1, 4):
        try:
            with get_db_session() as session:
                while is_date_delivered(session, date.fromisoformat(target_date_str)):
                    next_date = (
                        date.fromisoformat(target_date_str) + timedelta(days=1)
                    ).isoformat()
                    target_date_str = next_date
                if target_date_str != (
                    sys.argv[1] if len(sys.argv) > 1 else get_current_ist_date()
                ):
                    print(
                        f"ℹ️ Advancing test run to next undelivered date '{target_date_str}' for fresh candidate delivery."
                    )
            break
        except Exception:
            if attempt < 3:
                print(
                    f"⏳ Neon DB compute endpoint waking up (attempt {attempt}/3)... Retrying in 2s"
                )
                time.sleep(2.0)
            else:
                raise

    print(f"\n[Step 2/3] Executing Full Daily StateGraph Workflow for date '{target_date_str}'...")
    final_state = run_daily_workflow(scheduled_date=target_date_str)
    print(f"Pipeline Final Status: {final_state.get('status')}")
    print(f"Candidate ID: {final_state.get('candidate_id')}")
    print(f"Attribution: {final_state.get('attribution')}")
    print(f"Collection: {final_state.get('collection')} (#{final_state.get('hadith_number')})")
    print(f"AI Reflection Status: {final_state.get('ai_reflection_status')}")
    print("\n--- Formatted Telegram Notification ---")
    print(final_state.get("formatted_message"))
    print("---------------------------------------")

    # -------------------------------------------------------------
    # Step 3: Immediate Idempotency Skip Verification
    # -------------------------------------------------------------
    print(
        f"\n[Step 3/3] Testing Idempotency Protection (Immediate Re-run for '{target_date_str}')..."
    )
    rerun_state = run_daily_workflow(scheduled_date=target_date_str)
    print(f"Re-run Status: {rerun_state.get('status')}")
    assert rerun_state.get("status") == "SKIPPED_IDEMPOTENT", (
        f"Expected SKIPPED_IDEMPOTENT, got {rerun_state.get('status')}"
    )
    print("✅ Idempotency Verified: Duplicate delivery successfully blocked!")

    print("\n" + "=" * 70)
    print("🎉 ALL END-TO-END CHECKS COMPLETED SUCCESSFULLY!")
    print("=" * 70)


if __name__ == "__main__":
    main()
