# LangGraph Workflow Orchestration Package (`src/workflow/`)

This package implements the end-to-end daily delivery pipeline as a typed, observable **LangGraph StateGraph** with deterministic routing and fail-closed safety abort edges.

---

## Module Overview

| File | Purpose | Key Exports |
|---|---|---|
| **[`state.py`](state.py)** | Typed state dictionary definition flowing through all nodes | `DailyWorkflowState`, `create_initial_state()`, `get_current_ist_date()` |
| **[`nodes.py`](nodes.py)** | Pure, testable node functions executing pipeline steps | `WorkflowNodes`, `APPROVED_COLLECTIONS` |
| **[`graph.py`](graph.py)** | StateGraph assembly, conditional edge routers, and compiler | `build_daily_workflow_graph()`, `run_daily_workflow()` |
| **[`__init__.py`](__init__.py)** | Public package interface | Unified workflow exports |

---

## StateGraph Architecture & Routing

```mermaid
flowchart TD
    Start([Start Daily Trigger]) --> CheckIdempotency[Node: check_idempotency]
    CheckIdempotency -->|Already Delivered Today| SkipDelivery[End: SKIPPED_IDEMPOTENT]
    CheckIdempotency -->|Not Delivered Today| FetchCandidate[Node: fetch_candidate]
    FetchCandidate -->|No Candidates Available| AbortNoCandidate[End: ABORTED_NO_CANDIDATE]
    FetchCandidate -->|Candidate Found| VerifySafety[Node: verify_safety]
    VerifySafety -->|Invariant Failed| AbortSafety[End: ABORTED_VALIDATION_FAILED]
    VerifySafety -->|Invariant Passed| FormatMessage[Node: format_message]
    FormatMessage --> RecordDelivery[Node: record_delivery]
    RecordDelivery --> Completed([End: COMPLETED])
```

### Execution Example
```python
from src.workflow import run_daily_workflow

# Run daily execution for Asia/Kolkata date
final_state = run_daily_workflow(scheduled_date="2026-11-05")
print(final_state["status"])  # COMPLETED or SKIPPED_IDEMPOTENT
print(final_state["formatted_message"])
```