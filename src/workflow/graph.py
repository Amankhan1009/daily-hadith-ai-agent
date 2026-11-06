"""
LangGraph Daily Hadith StateGraph Construction.

Assembles the directed state graph with deterministic routing, conditional
branching, and fail-closed safety abort edges.
"""

from datetime import date
from typing import Literal, Optional
from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph
from sqlalchemy.orm import Session

from src.guardrails import ReflectionValidator
from src.llm import GroqReflectionClient
from src.workflow.nodes import WorkflowNodes
from src.workflow.state import DailyWorkflowState, create_initial_state

from src.delivery import TelegramClient

# ---------------------------------------------------------------------------
# Conditional Edge Routers
# ---------------------------------------------------------------------------

def route_after_idempotency(
    state: DailyWorkflowState,
) -> Literal["fetch_candidate", "__end__"]:
    """
    Decide whether to fetch candidate or halt if delivery was already completed.
    """
    if state.get("is_idempotent", False):
        return END
    return "fetch_candidate"


def route_after_fetch(
    state: DailyWorkflowState,
) -> Literal["verify_safety", "__end__"]:
    """
    Decide whether to verify safety or halt if no candidate was found in queue.
    """
    if state.get("status") == "ABORTED_NO_CANDIDATE" or state.get("candidate_id") is None:
        return END
    return "verify_safety"


def route_after_verification(
    state: DailyWorkflowState,
) -> Literal["generate_reflection", "__end__"]:
    """
    Decide whether to proceed to reflection generation or abort fail-closed.
    """
    if not state.get("verification_passed", False):
        return END
    return "generate_reflection"


# ---------------------------------------------------------------------------
# StateGraph Builder
# ---------------------------------------------------------------------------

from src.delivery import TelegramClient


def build_daily_workflow_graph(
    session: Optional[Session] = None,
    llm_client: Optional[GroqReflectionClient] = None,
    validator: Optional[ReflectionValidator] = None,
    telegram_client: Optional[TelegramClient] = None,
) -> CompiledStateGraph:
    """
    Construct and compile the Daily Hadith LangGraph workflow with Telegram delivery.
    """
    nodes = WorkflowNodes(
        session=session,
        llm_client=llm_client,
        validator=validator,
        telegram_client=telegram_client,
    )
    workflow = StateGraph(DailyWorkflowState)

    # 1. Register Graph Nodes
    workflow.add_node("check_idempotency", nodes.check_idempotency_node)
    workflow.add_node("fetch_candidate", nodes.fetch_candidate_node)
    workflow.add_node("verify_safety", nodes.verify_safety_node)
    workflow.add_node("generate_reflection", nodes.generate_reflection_node)
    workflow.add_node("validate_guardrails", nodes.validate_guardrails_node)
    workflow.add_node("format_message", nodes.format_message_node)
    workflow.add_node("deliver_telegram", nodes.deliver_telegram_node)
    workflow.add_node("record_delivery", nodes.record_delivery_node)

    # 2. Set Entry Point
    workflow.set_entry_point("check_idempotency")

    # 3. Add Conditional Routing Edges
    workflow.add_conditional_edges(
        "check_idempotency",
        route_after_idempotency,
        {
            "fetch_candidate": "fetch_candidate",
            END: END,
        },
    )

    workflow.add_conditional_edges(
        "fetch_candidate",
        route_after_fetch,
        {
            "verify_safety": "verify_safety",
            END: END,
        },
    )

    workflow.add_conditional_edges(
        "verify_safety",
        route_after_verification,
        {
            "generate_reflection": "generate_reflection",
            END: END,
        },
    )

    # 4. Add Linear Edges
    workflow.add_edge("generate_reflection", "validate_guardrails")
    workflow.add_edge("validate_guardrails", "format_message")
    workflow.add_edge("format_message", "deliver_telegram")
    workflow.add_edge("deliver_telegram", "record_delivery")
    workflow.add_edge("record_delivery", END)

    return workflow.compile()


def run_daily_workflow(
    scheduled_date: Optional[str | date] = None,
    session: Optional[Session] = None,
    llm_client: Optional[GroqReflectionClient] = None,
    validator: Optional[ReflectionValidator] = None,
    telegram_client: Optional[TelegramClient] = None,
) -> DailyWorkflowState:
    """
    Execute a complete run of the Daily Hadith state graph.
    """
    graph = build_daily_workflow_graph(
        session=session,
        llm_client=llm_client,
        validator=validator,
        telegram_client=telegram_client,
    )
    initial_state = create_initial_state(scheduled_date=scheduled_date)
    final_state = graph.invoke(initial_state)
    return final_state

