"""Workflow routing policy for claim processing graph transitions."""

from dataclasses import dataclass
from typing import Any

from workflow.contracts import (
    AGENT_REVIEW,
    COMPLETENESS_CHECK,
    END,
    FINAL_DECISION,
    HUMAN_REVIEW,
    OCR_EXTRACTION,
    OCR_STAGE_PHASE1_CLASSIFIED,
    OCR_STAGE_PHASE2_EXTRACTED,
    QUALITY_CHECK,
    SEVERITY_ESCALATION,
    STAGE_COMPLETENESS,
    STAGE_FINAL,
    STAGE_NONE,
    STAGE_QUALITY,
    GraphState,
)

VALID_AGENT_DECISIONS = frozenset({"accept", "reject", "accept_with_edit"})


@dataclass(frozen=True)
class StagePolicy:
    """Routing metadata for one workflow stage."""

    stage: str
    result_key: str
    edited_result_key: str | None
    node: str
    next_after_accept: str
    next_after_reject: str
    next_after_accept_with_edit: str
    next_after_human_edit: str
    active_stage_after_auto_review: str
    supports_agent_review: bool = True
    requires_phase2_ocr: bool = False


@dataclass(frozen=True)
class ReviewTarget:
    """Agent result selected for verifier or human review."""

    stage: str
    result_key: str
    result: dict[str, Any]
    policy: StagePolicy


STAGE_POLICIES: dict[str, StagePolicy] = {
    STAGE_COMPLETENESS: StagePolicy(
        stage=STAGE_COMPLETENESS,
        result_key="agent_1_result",
        edited_result_key="edited_agent_1_result",
        node=COMPLETENESS_CHECK,
        next_after_accept=QUALITY_CHECK,
        next_after_reject=FINAL_DECISION,
        next_after_accept_with_edit=AGENT_REVIEW,
        next_after_human_edit=COMPLETENESS_CHECK,
        active_stage_after_auto_review=STAGE_QUALITY,
        requires_phase2_ocr=True,
    ),
    STAGE_QUALITY: StagePolicy(
        stage=STAGE_QUALITY,
        result_key="agent_2_result",
        edited_result_key="edited_agent_2_result",
        node=QUALITY_CHECK,
        next_after_accept=FINAL_DECISION,
        next_after_reject=FINAL_DECISION,
        next_after_accept_with_edit=AGENT_REVIEW,
        next_after_human_edit=QUALITY_CHECK,
        active_stage_after_auto_review=STAGE_NONE,
    ),
    STAGE_FINAL: StagePolicy(
        stage=STAGE_FINAL,
        result_key="final_result",
        edited_result_key=None,
        node=FINAL_DECISION,
        next_after_accept=HUMAN_REVIEW,
        next_after_reject=HUMAN_REVIEW,
        next_after_accept_with_edit=HUMAN_REVIEW,
        next_after_human_edit=QUALITY_CHECK,
        active_stage_after_auto_review=STAGE_NONE,
        supports_agent_review=False,
    ),
}


def stage_policy(stage: str | None, *, default_stage: str = STAGE_QUALITY) -> StagePolicy:
    """Return routing metadata for a workflow stage."""
    return STAGE_POLICIES.get(stage or "", STAGE_POLICIES[default_stage])


def decision_from_result(result: dict | None) -> str:
    """Extract a normalized routing decision from an agent result."""
    if not result:
        return "reject"

    decision = result.get("decision")
    if decision in VALID_AGENT_DECISIONS:
        return str(decision)

    if result.get("valid", False):
        return "accept"

    issues = result.get("issues", []) or []
    has_critical_or_high = any(
        i.get("severity") in SEVERITY_ESCALATION for i in issues if isinstance(i, dict)
    )
    return "reject" if has_critical_or_high else "accept_with_edit"


def human_decision_from_state(state: GraphState) -> str:
    """Return normalized human-review decision from workflow state."""
    result = state.get("human_review_result", {}) or {}
    decision = str(result.get("decision", "reject")).lower()

    if decision in ("accept", "approve"):
        return "approve"
    if decision in ("reject", "denied"):
        return "reject"
    if decision == "edit":
        return "edit"
    return "reject"


def review_stage_from_state(state: GraphState) -> str:
    """Return explicit review stage with legacy current_step fallback."""
    explicit_stage = state.get("review_stage")
    if explicit_stage and explicit_stage != STAGE_NONE:
        return explicit_stage

    current_step = state.get("current_step", "")
    if STAGE_COMPLETENESS in current_step:
        return STAGE_COMPLETENESS
    if STAGE_QUALITY in current_step:
        return STAGE_QUALITY
    if STAGE_FINAL in current_step or state.get("final_result"):
        return STAGE_FINAL
    return STAGE_QUALITY


def result_for_stage(state: GraphState, stage: str) -> dict[str, Any]:
    """Return the current result for a stage, preferring human-edited data."""
    policy = stage_policy(stage)
    original_result = state.get(policy.result_key) or {}

    if not policy.edited_result_key:
        return original_result

    edited_result = state.get(policy.edited_result_key)
    if edited_result is not None:
        return edited_result
    return original_result


def review_target_from_state(state: GraphState) -> ReviewTarget:
    """Return the assessment result targeted by the verifier gate."""
    stage = review_stage_from_state(state)
    policy = stage_policy(stage)
    if not policy.supports_agent_review:
        policy = stage_policy(STAGE_QUALITY)

    return ReviewTarget(
        stage=policy.stage,
        result_key=policy.result_key,
        result=state.get(policy.result_key) or {},
        policy=policy,
    )


def next_after_stage_accept(state: GraphState, policy: StagePolicy) -> str:
    """Return the next node after a stage is accepted."""
    if policy.requires_phase2_ocr and state.get("ocr_stage") == OCR_STAGE_PHASE1_CLASSIFIED:
        return OCR_EXTRACTION
    return policy.next_after_accept


def next_after_stage_assessment(state: GraphState, stage: str) -> str:
    """Route after an assessment stage based on its agent result."""
    policy = stage_policy(stage)
    decision = decision_from_result(result_for_stage(state, stage))

    if decision == "accept":
        return next_after_stage_accept(state, policy)
    if decision == "accept_with_edit":
        return policy.next_after_accept_with_edit
    return policy.next_after_reject


def next_after_agent_review(state: GraphState) -> str:
    """Route after verifier gate based on policy-owned review target metadata."""
    target = review_target_from_state(state)
    if target.result.get("is_auto_reviewed", False):
        return next_after_stage_accept(state, target.policy)
    return HUMAN_REVIEW


def active_stage_after_auto_review(stage: str) -> str:
    """Return active_stage value after verifier auto-approves a stage."""
    return stage_policy(stage).active_stage_after_auto_review


def next_after_human_stage_review(state: GraphState, stage: str) -> str:
    """Route after human review for completeness or quality stages."""
    policy = stage_policy(stage)
    decision = human_decision_from_state(state)

    if decision == "approve":
        return next_after_stage_accept(state, policy)
    if decision == "edit":
        return policy.next_after_human_edit
    return policy.next_after_reject


def next_after_human_review(state: GraphState) -> str:
    """Route after human review based on the reviewed stage and decision."""
    result = state.get("human_review_result", {}) or {}
    stage = result.get("stage") or review_stage_from_state(state)

    if stage in (STAGE_COMPLETENESS, STAGE_QUALITY):
        return next_after_human_stage_review(state, stage)

    decision = human_decision_from_state(state)
    if decision in ("approve", "reject"):
        return END
    return stage_policy(STAGE_FINAL).next_after_human_edit


def next_after_ocr_extraction(state: GraphState) -> str:
    """Route after OCR phase 2 extraction."""
    if state.get("ocr_stage") == OCR_STAGE_PHASE2_EXTRACTED:
        return QUALITY_CHECK
    return FINAL_DECISION
