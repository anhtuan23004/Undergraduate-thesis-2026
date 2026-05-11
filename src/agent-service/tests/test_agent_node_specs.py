"""Tests for agent node role specifications."""

from agents.node_specs import (
    AGENT_NODE_SPECS,
    ROLE_COMPLETENESS,
    ROLE_DECISION,
    ROLE_QUALITY,
    ROLE_VERIFIER,
    agent_node_spec,
    review_stage_after_agent_result,
)
from graphs.workflow_policy import stage_policy
from schemas.agent_outputs import AssessmentOutput, FinalDecisionOutput
from schemas.verifier_outputs import VerifierOutput


def test_agent_node_specs_cover_current_roles():
    assert set(AGENT_NODE_SPECS) == {
        ROLE_COMPLETENESS,
        ROLE_QUALITY,
        ROLE_DECISION,
        ROLE_VERIFIER,
    }


def test_assessment_specs_match_workflow_stage_policy_keys():
    completeness = agent_node_spec(ROLE_COMPLETENESS)
    quality = agent_node_spec(ROLE_QUALITY)
    final = agent_node_spec(ROLE_DECISION)

    assert completeness.output_key == stage_policy("completeness").result_key
    assert quality.output_key == stage_policy("quality").result_key
    assert final.output_key == stage_policy("final").result_key


def test_agent_node_specs_keep_role_runtime_metadata_together():
    completeness = agent_node_spec(ROLE_COMPLETENESS)
    verifier = agent_node_spec(ROLE_VERIFIER)

    assert completeness.skill_name == "completeness_agent"
    assert completeness.prompt_name == "completeness_agent"
    assert completeness.display_name == "CompletenessAgent"
    assert completeness.schema_class is AssessmentOutput
    assert completeness.active_stage == "completeness"
    assert completeness.review_stage_on_accept_with_edit == "completeness"

    assert verifier.output_key == "verifier_result"
    assert verifier.schema_class is VerifierOutput
    assert verifier.active_stage == "none"


def test_decision_spec_uses_final_output_schema():
    decision = agent_node_spec(ROLE_DECISION)

    assert decision.prompt_name == "final_agent"
    assert decision.output_key == "final_result"
    assert decision.schema_class is FinalDecisionOutput


def test_review_stage_after_agent_result_only_marks_accept_with_edit():
    completeness = agent_node_spec(ROLE_COMPLETENESS)

    assert (
        review_stage_after_agent_result(completeness, {"decision": "accept_with_edit"})
        == "completeness"
    )
    assert review_stage_after_agent_result(completeness, {"decision": "accept"}) == "none"
