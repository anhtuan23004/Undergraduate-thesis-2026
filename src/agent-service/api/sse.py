"""Server-sent event helpers for workflow streaming endpoints."""

import json
from collections.abc import AsyncGenerator
from typing import Any

import structlog
from services.workflow_state import build_workflow_response, extract_pause_state

logger = structlog.get_logger()

# WHY: Map LangGraph node names to the UI step names used by the frontend.
NODE_TO_STEP = {
    "completeness_check": "completeness",
    "ocr_extraction": "ocr_extraction",
    "agent_review": "agent_review",
    "quality_check": "quality",
    "human_review": "human_review",
    "final_decision": "final_decision",
}


def sse_event(event_type: str, payload: dict) -> str:
    """Format a payload as an SSE event string."""
    data = json.dumps(payload, ensure_ascii=False, default=str)
    return f"event: {event_type}\ndata: {data}\n\n"


async def stream_graph_events(
    graph: Any,
    input_state: Any,
    config: dict,
) -> AsyncGenerator[str, None]:
    """Yield SSE events while the graph executes."""
    try:
        async for event in graph.astream_events(input_state, config=config, version="v2"):
            kind = event.get("event", "")
            name = event.get("name", "")
            step_key = NODE_TO_STEP.get(name)

            if kind == "on_chain_start" and step_key:
                yield sse_event("node_start", {"step": step_key, "node": name})

            elif kind == "on_chain_end" and step_key:
                snapshot = await graph.aget_state(config)
                state_values = snapshot.values if snapshot else {}
                is_pending, is_paused, pause_at = extract_pause_state(snapshot)
                partial = build_workflow_response(state_values, is_pending, is_paused, pause_at)
                yield sse_event(
                    "node_end",
                    {
                        "step": step_key,
                        "node": name,
                        "state": partial,
                    },
                )

        snapshot = await graph.aget_state(config)
        state_values = snapshot.values if snapshot else {}
        is_pending, is_paused, pause_at = extract_pause_state(snapshot)
        final = build_workflow_response(state_values, is_pending, is_paused, pause_at)
        yield sse_event("done", final)

    except Exception as exc:
        logger.error("Streaming error", error=str(exc))
        yield sse_event("error", {"error": str(exc)})
