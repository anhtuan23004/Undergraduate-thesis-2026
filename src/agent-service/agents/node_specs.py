"""Agent node role specifications."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from graphs.constants import (
    STAGE_COMPLETENESS,
    STAGE_FINAL,
    STAGE_NONE,
    STAGE_QUALITY,
)
from pydantic import BaseModel
from schemas.agent_outputs import AssessmentOutput, FinalDecisionOutput
from schemas.verifier_outputs import VerifierOutput

from agents.prompt_builders import (
    build_completeness_prompt,
    build_decision_prompt,
    build_quality_prompt,
    build_verifier_prompt,
)

ROLE_COMPLETENESS = "completeness"
ROLE_QUALITY = "quality"
ROLE_DECISION = "decision"
ROLE_VERIFIER = "verifier"


@dataclass(frozen=True)
class AgentNodeSpec:
    """Role metadata required to build one workflow agent node."""

    role: str
    skill_name: str
    prompt_name: str
    display_name: str
    output_key: str
    schema_class: type[BaseModel]
    prompt_builder: Callable[[dict[str, Any], str], str]
    active_stage: str
    review_stage_on_accept_with_edit: str = STAGE_NONE


AGENT_NODE_SPECS: dict[str, AgentNodeSpec] = {
    ROLE_COMPLETENESS: AgentNodeSpec(
        role=ROLE_COMPLETENESS,
        skill_name="completeness_agent",
        prompt_name="completeness_agent",
        display_name="CompletenessAgent",
        output_key="agent_1_result",
        schema_class=AssessmentOutput,
        prompt_builder=build_completeness_prompt,
        active_stage=STAGE_COMPLETENESS,
        review_stage_on_accept_with_edit=STAGE_COMPLETENESS,
    ),
    ROLE_QUALITY: AgentNodeSpec(
        role=ROLE_QUALITY,
        skill_name="quality_agent",
        prompt_name="quality_agent",
        display_name="QualityAgent",
        output_key="agent_2_result",
        schema_class=AssessmentOutput,
        prompt_builder=build_quality_prompt,
        active_stage=STAGE_QUALITY,
        review_stage_on_accept_with_edit=STAGE_QUALITY,
    ),
    ROLE_DECISION: AgentNodeSpec(
        role=ROLE_DECISION,
        skill_name="decision_agent",
        prompt_name="final_agent",
        display_name="FinalAgent",
        output_key="final_result",
        schema_class=FinalDecisionOutput,
        prompt_builder=build_decision_prompt,
        active_stage=STAGE_FINAL,
    ),
    ROLE_VERIFIER: AgentNodeSpec(
        role=ROLE_VERIFIER,
        skill_name="verifier_agent",
        prompt_name="verifier_agent",
        display_name="VerifierAgent",
        output_key="verifier_result",
        schema_class=VerifierOutput,
        prompt_builder=build_verifier_prompt,
        active_stage=STAGE_NONE,
    ),
}


def agent_node_spec(role: str) -> AgentNodeSpec:
    """Return the agent node spec for a workflow role."""
    return AGENT_NODE_SPECS[role]


def review_stage_after_agent_result(spec: AgentNodeSpec, result: dict[str, Any]) -> str:
    """Return review stage implied by an agent output."""
    if result.get("decision") != "accept_with_edit":
        return STAGE_NONE
    return spec.review_stage_on_accept_with_edit
