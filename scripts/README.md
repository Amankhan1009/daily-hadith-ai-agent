# Operational Scripts (`scripts/`)

This directory contains standalone operational and verification scripts for the **Daily Hadith AI Agent**.

---

## Script Overview

| Script | Purpose | Execution |
|---|---|---|
| **[`register_webhook.py`](register_webhook.py)** | CLI to inspect, configure, and delete the Telegram inbound webhook for cloud deployments. | `python -m scripts.register_webhook --info` |
| **[`test_e2e_workflow.py`](test_e2e_workflow.py)** | End-to-end live test verifying Groq LLM reflections, LangGraph StateGraph pipeline, Neon PostgreSQL queue consumption, and daily delivery idempotency. | `.venv/bin/python scripts/test_e2e_workflow.py` |

