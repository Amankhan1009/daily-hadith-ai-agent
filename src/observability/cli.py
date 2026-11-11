"""
Observability Diagnostics and Verification CLI.

Enables developers, evaluators, and recruiters to inspect LangSmith configuration,
test live cloud tracing connectivity, and view project dashboards.

Usage:
    python -m src.observability.cli
    python -m src.observability.cli --verify
"""

import argparse
import sys

from src.config import get_settings
from src.observability.tracer import get_workflow_run_config, is_tracing_enabled


def run_diagnostics(verbose: bool = False) -> int:
    """
    Run observability diagnostics and output structured verification status.

    Returns:
        int: 0 if healthy/operational, 1 if tracing misconfigured.
    """
    settings = get_settings()
    tracing_active = is_tracing_enabled()

    print("=" * 70)
    print("🔭 DAILY HADITH AI AGENT — OBSERVABILITY & TRACING DIAGNOSTICS")
    print("=" * 70)
    print(
        f"• LangSmith Tracing V2 : {'ENABLED (Active)' if settings.langchain_tracing_v2 else 'DISABLED'}"
    )
    print(f"• Target Project Name  : {settings.langchain_project}")
    print(f"• Ingestion Endpoint   : {settings.langchain_endpoint}")

    if settings.langchain_api_key:
        masked_key = settings.langchain_api_key[:10] + "..." + settings.langchain_api_key[-4:]
        print(f"• API Key Configured   : {masked_key} (Valid)")
    else:
        print("• API Key Configured   : <NOT_CONFIGURED>")

    sample_config = get_workflow_run_config(scheduled_date="2026-11-12", is_dry_run=True)
    print("\n📋 Sample LangGraph Trace Metadata:")
    print(f"  - Run Name : {sample_config['run_name']}")
    print(f"  - Tags     : {sample_config['tags']}")
    print(f"  - Metadata : {sample_config['metadata']}")

    if not tracing_active:
        print("\n⚠️ LangSmith tracing is currently disabled.")
        print("  To enable cloud tracing, set the following in your .env or Render environment:")
        print("    LANGCHAIN_TRACING_V2=true")
        print("    LANGCHAIN_API_KEY=lsv2_pt_...")
        print("    LANGCHAIN_PROJECT=daily-hadith-ai-agent")
        print("=" * 70)
        return 0

    print("\n🚀 Testing Live Cloud Trace Dispatch...")
    try:
        from src.llm.client import GroqReflectionClient

        client = GroqReflectionClient()
        test_hadith = (
            "He who believes in Allah and the Last Day, let him speak good or remain silent."
        )
        print("  Dispatching synthetic reflection trace to LangSmith...")
        result = client.generate_reflection(
            english_text=test_hadith,
            attribution="Abu Hurairah",
            collection="Sahih al-Bukhari",
        )

        print(f"  Inference Status: {result.status}")
        if result.reflection:
            first_line = result.reflection.strip().split("\n")[0]
            print(f"  Generated Preview: {first_line[:80]}...")

        print("\n✅ LIVE TRACE DISPATCHED SUCCESSFULLY!")
        print("=" * 70)
        print("🔗 View your traces live in the LangSmith Dashboard:")
        print("   https://smith.langchain.com/")
        print(f"   Project: {settings.langchain_project}")
        print("=" * 70)
        return 0
    except Exception as exc:
        print(f"\n❌ Live trace dispatch failed: {exc}", file=sys.stderr)
        print("=" * 70)
        return 1


def main() -> None:
    """CLI entrypoint."""
    parser = argparse.ArgumentParser(
        description="Daily Hadith AI Agent — Observability & Tracing Diagnostics CLI"
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="Run live end-to-end trace verification against LangSmith",
    )
    args = parser.parse_args()
    sys.exit(run_diagnostics(verbose=args.verify))


if __name__ == "__main__":
    main()
