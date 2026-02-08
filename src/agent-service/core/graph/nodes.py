"""Node implementations for ReAct agent graph."""
import json
from typing import Dict, Any, List
from datetime import datetime

from core.graph.state import AgentState
from core.llm.client import LLMClient
from tools.registry import ToolRegistry
from app.config import settings


llm_client = LLMClient()
tool_registry = ToolRegistry()


async def observe_node(state: AgentState) -> Dict[str, Any]:
    """Gather observations from extracted data and context.

    This is the first step in the ReAct loop - collecting all relevant
    information about the claim.
    """
    observations = []

    # Document extraction observations
    extracted = state["extracted_data"]

    if extracted.get("patient"):
        observations.append(f"Patient: {extracted['patient']}")

    if extracted.get("diagnosis_codes"):
        codes = extracted["diagnosis_codes"]
        observations.append(f"Diagnosis codes: {', '.join(codes)}")

    if extracted.get("total_amount"):
        observations.append(f"Claim amount: {extracted['total_amount']} VND")

    if extracted.get("hospital"):
        observations.append(f"Hospital: {extracted['hospital']}")

    # Policy context observations
    if state["retrieved_context"]:
        context_count = len(state["retrieved_context"])
        observations.append(f"Retrieved {context_count} relevant policy documents")

    # Tool result observations
    if state["tool_results"]:
        last_result = state["tool_results"][-1]
        observations.append(f"Last tool result: {last_result.get('summary', '')}")

    # If no observations yet, this is the start
    if not observations:
        observations.append("Starting claim processing. Need to gather information.")

    return {
        "observations": observations
    }


async def think_node(state: AgentState) -> Dict[str, Any]:
    """Generate reasoning using LLM.

    Based on observations, decide what to do next.
    """
    # Build prompt for reasoning
    prompt = _build_think_prompt(state)

    # Get LLM response
    response = await llm_client.generate(
        prompt=prompt,
        system_prompt=_get_system_prompt(),
        temperature=0.3
    )

    thought = response.strip()

    return {
        "thoughts": [thought]
    }


async def act_node(state: AgentState) -> Dict[str, Any]:
    """Execute tool based on the thought.

    Parse the thought to determine which tool to call.
    """
    thought = state["thoughts"][-1] if state["thoughts"] else ""

    # Determine which tool to use based on thought
    tool_name, tool_input = _parse_tool_from_thought(thought, state)

    # Get tool from registry
    tool = tool_registry.get(tool_name)

    if not tool:
        # No valid tool found
        return {
            "actions": [{
                "tool": "none",
                "input": {},
                "error": f"Tool '{tool_name}' not found"
            }],
            "tool_results": [{
                "error": f"Unknown tool: {tool_name}",
                "summary": "No tool executed"
            }]
        }

    # Execute tool
    try:
        result = await tool.arun(**tool_input)
        action = {
            "tool": tool_name,
            "input": tool_input,
            "timestamp": datetime.now().isoformat()
        }
        tool_result = {
            "tool": tool_name,
            "result": result,
            "summary": _summarize_result(result),
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        action = {
            "tool": tool_name,
            "input": tool_input,
            "error": str(e)
        }
        tool_result = {
            "tool": tool_name,
            "error": str(e),
            "summary": f"Tool execution failed: {e}"
        }

    return {
        "actions": [action],
        "tool_results": [tool_result]
    }


async def reflect_node(state: AgentState) -> Dict[str, Any]:
    """Evaluate action results and decide whether to continue.

    This is the reflection phase of ReAct.
    """
    # Get the latest tool result
    tool_results = state.get("tool_results", [])
    if not tool_results:
        # No tools executed yet
        return {
            "reflections": ["No actions taken yet. Need to gather information."],
            "should_continue": True,
            "iteration_count": state["iteration_count"] + 1
        }

    last_result = tool_results[-1]

    # Check if we have enough information to decide
    has_policy_info = any(
        r.get("tool") == "policy_check" and not r.get("error")
        for r in tool_results
    )
    has_icd_info = any(
        r.get("tool") == "icd_lookup" and not r.get("error")
        for r in tool_results
    )

    # Build reflection
    reflections = []
    should_continue = True

    if last_result.get("error"):
        reflections.append(f"Last action failed: {last_result['error']}. Will try different approach.")
    else:
        reflections.append(f"Successfully executed {last_result['tool']}: {last_result.get('summary', '')}")

    # Decide whether to continue
    if has_policy_info and has_icd_info:
        # Have both policy and diagnosis info - can decide
        reflections.append("Have sufficient information to make decision.")
        should_continue = False
    elif state["iteration_count"] >= state["max_iterations"] - 1:
        # Max iterations reached
        reflections.append("Maximum iterations reached. Making best-effort decision.")
        should_continue = False
    else:
        # Need more information
        missing = []
        if not has_policy_info:
            missing.append("policy coverage")
        if not has_icd_info:
            missing.append("diagnosis validation")
        reflections.append(f"Still need: {', '.join(missing)}")
        should_continue = True

    return {
        "reflections": reflections,
        "should_continue": should_continue,
        "iteration_count": state["iteration_count"] + 1
    }


async def decide_node(state: AgentState) -> Dict[str, Any]:
    """Make final decision on the claim.

    This is the terminal node that produces the final output.
    """
    # Build decision prompt
    prompt = _build_decide_prompt(state)

    # Get structured output from LLM
    response = await llm_client.generate_json(
        prompt=prompt,
        system_prompt=_get_decision_system_prompt(),
        schema={
            "type": "object",
            "properties": {
                "decision": {"type": "string", "enum": ["APPROVE", "REJECT", "PENDING"]},
                "confidence_score": {"type": "number", "minimum": 0, "maximum": 1},
                "amount_recommended": {"type": "number"},
                "reasoning": {"type": "string"},
                "evidence": {"type": "array", "items": {"type": "object"}},
                "risks": {"type": "array", "items": {"type": "string"}}
            },
            "required": ["decision", "confidence_score", "amount_recommended", "reasoning"]
        }
    )

    return {
        "decision": response.get("decision", "PENDING"),
        "confidence_score": response.get("confidence_score", 0.0),
        "amount_recommended": response.get("amount_recommended", 0.0),
        "reasoning": response.get("reasoning", ""),
        "evidence": response.get("evidence", []),
        "risks": response.get("risks", [])
    }


# Helper functions

def _build_think_prompt(state: AgentState) -> str:
    """Build prompt for thinking node."""
    lines = [
        "You are processing a health insurance claim. Based on the following information, decide what to do next.",
        "",
        "## Observations:",
    ]

    for obs in state.get("observations", []):
        lines.append(f"- {obs}")

    if state.get("thoughts"):
        lines.extend(["", "## Previous Thoughts:"])
        for i, thought in enumerate(state["thoughts"][-3:], 1):
            lines.append(f"{i}. {thought}")

    if state.get("tool_results"):
        lines.extend(["", "## Previous Actions:"])
        for result in state["tool_results"][-3:]:
            tool = result.get("tool", "unknown")
            summary = result.get("summary", "no result")
            lines.append(f"- {tool}: {summary}")

    lines.extend([
        "",
        "## Available Tools:",
        "- icd_lookup: Validate ICD-10 diagnosis codes and check coverage",
        "- policy_check: Check policy terms and coverage limits",
        "- coverage_calc: Calculate eligible claim amount",
        "- document_query: Query extracted document fields",
        "",
        "## Instructions:",
        "Think step by step about what information you need to make a decision.",
        "If you need more information, specify which tool to use and why.",
        "If you have enough information, say 'READY_TO_DECIDE'.",
        "",
        "Your thought:"
    ])

    return "\n".join(lines)


def _get_system_prompt() -> str:
    """Get system prompt for thinking."""
    return """You are an expert insurance claims analyst. Your job is to review health insurance claims and decide whether to approve, reject, or pend them for human review.

Be thorough and consider:
1. Is the diagnosis covered by the policy?
2. Are the claimed amounts reasonable?
3. Are all required documents present?
4. Are there any policy exclusions that apply?

Think step by step and explain your reasoning."""


def _parse_tool_from_thought(thought: str, state: AgentState) -> tuple:
    """Parse which tool to use from the thought text."""
    thought_lower = thought.lower()

    # Check for explicit tool mentions
    if "icd" in thought_lower or "diagnosis" in thought_lower or "code" in thought_lower:
        return "icd_lookup", {
            "codes": state["extracted_data"].get("diagnosis_codes", [])
        }

    if "policy" in thought_lower or "coverage" in thought_lower or "limit" in thought_lower:
        return "policy_check", {
            "policy_number": state["policy_number"],
            "query": "coverage for diagnosis"
        }

    if "calculate" in thought_lower or "amount" in thought_lower or "eligible" in thought_lower:
        return "coverage_calc", {
            "claimed_amounts": [state["extracted_data"].get("total_amount", 0)],
            "policy_number": state["policy_number"]
        }

    if "document" in thought_lower or "field" in thought_lower or "missing" in thought_lower:
        return "document_query", {
            "claim_id": state["claim_id"],
            "fields": ["patient", "hospital", "diagnosis"]
        }

    # Default: try to get policy info
    return "policy_check", {
        "policy_number": state["policy_number"],
        "query": "general coverage"
    }


def _summarize_result(result: Any) -> str:
    """Create a brief summary of tool result."""
    if isinstance(result, dict):
        if "summary" in result:
            return result["summary"]
        elif "status" in result:
            return f"Status: {result['status']}"
        else:
            return f"Result has {len(result)} fields"
    return str(result)[:100]


def _build_decide_prompt(state: AgentState) -> str:
    """Build prompt for final decision."""
    lines = [
        "Make a final decision on this insurance claim based on all gathered information.",
        "",
        "## Claim Information:",
        f"Claim ID: {state['claim_id']}",
        f"Policy Number: {state['policy_number']}",
        "",
        "## Extracted Data:",
        json.dumps(state["extracted_data"], indent=2, ensure_ascii=False),
        "",
        "## Reasoning Process:",
    ]

    for i, thought in enumerate(state.get("thoughts", []), 1):
        lines.append(f"Step {i}: {thought}")

    lines.extend([
        "",
        "## Tool Results:",
    ])

    for result in state.get("tool_results", []):
        tool = result.get("tool", "unknown")
        lines.append(f"\n{tool}:")
        if "result" in result:
            lines.append(json.dumps(result["result"], indent=2, ensure_ascii=False)[:500])

    lines.extend([
        "",
        "## Instructions:",
        "Provide your decision in JSON format with the following fields:",
        "- decision: APPROVE, REJECT, or PENDING",
        "- confidence_score: number between 0 and 1",
        "- amount_recommended: number (VND)",
        "- reasoning: detailed explanation (in Vietnamese if possible)",
        "- evidence: array of supporting evidence",
        "- risks: array of potential risks or concerns",
    ])

    return "\n".join(lines)


def _get_decision_system_prompt() -> str:
    """Get system prompt for decision."""
    return """You are a senior insurance claims adjudicator with 20 years of experience.

Your job is to make final decisions on health insurance claims. Be fair, thorough, and consistent.

Decision guidelines:
- APPROVE: If the claim is valid, within policy limits, and all documentation is complete
- REJECT: If the claim is not covered by policy, fraudulent, or missing critical information
- PENDING: If human review is needed (high value, complex case, or unclear coverage)

Always provide clear reasoning for your decision."""