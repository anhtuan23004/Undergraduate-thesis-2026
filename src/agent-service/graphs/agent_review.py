"""Agent Review Node for automated cross-verification of agent outputs.

This module implements the AgentReviewNode which acts as an automated
verification layer. When an assessment agent returns `accept_with_edit`,
the workflow routes here first. The VerifierAgent re-evaluates the
proposed result and identified issues using available tools but does not
apply updates itself. If confident (score > 0.9, configurable) and it
determines that no medium, high, or critical issues remain, it marks the
result as auto-reviewed and the workflow proceeds without human
intervention; otherwise, it escalates to human review.
"""

from typing import Any

import structlog
from agents.factory import VerifierAgentFactory
from config import settings

from graphs.constants import (
    SEVERITY_REVIEW_REQUIRED,
    STAGE_COMPLETENESS,
    STAGE_NONE,
    STAGE_QUALITY,
    STATUS_RUNNING,
    STATUS_WAITING_HUMAN,
)
from graphs.state import GraphState

logger = structlog.get_logger()

REASON_HARD_CONSTRAINTS_FAILED = "hard_constraints_failed"
REASON_VERIFIER_CONTRADICTIONS = "verifier_contradictions"
REASON_VERIFIER_FAILED = "verifier_failed"
REASON_LOW_CONFIDENCE = "low_confidence"


class AgentReviewNode:
    """Node for automated agent-based review of minor issues.

    Sitting between assessment agents and human review, this node
    upgrades the review logic from simple confidence checks to
    active cross-verification using a skeptical VerifierAgent
    and hard logic constraints.
    """

    def __init__(self, llm_client: Any) -> None:
        """Initialize the AgentReviewNode.

        Args:
            llm_client: Client for LLM interactions.
        """
        self.llm_client = llm_client
        self.verifier_factory = VerifierAgentFactory(llm_client)
        self.verifier_agent = self.verifier_factory.create_verifier_agent()
        self.amount_threshold = settings.AGENT_REVIEW_AMOUNT_THRESHOLD
        self.confidence_threshold = settings.AGENT_REVIEW_CONFIDENCE_THRESHOLD

    async def run(self, state: GraphState) -> dict[str, Any]:  # noqa: C901
        """Execute the agent review node.

        Examines the current agent result, checks confidence and issue
        severity, and decides whether to auto-approve or escalate to
        human review.

        Args:
            state: Current graph state.

        Returns:
            Dictionary with updated agent result and history.
        """
        stage = self._review_stage(state)
        if stage == STAGE_COMPLETENESS:
            agent_result = state.get("agent_1_result") or {}
            result_key = "agent_1_result"
        else:
            agent_result = state.get("agent_2_result") or {}
            result_key = "agent_2_result"

        confidence = agent_result.get("confidence_score", 0.0)
        issues = agent_result.get("issues", []) or []
        suggested_updates = agent_result.get("suggested_updates", []) or []

        # WHY: 1. Hard Constraints Check
        evidence = agent_result.get("evidence") or {}
        total_amount = evidence.get("total_claim_amount") or 0

        total_amount = self._parse_claim_amount(total_amount)

        has_high_risk_issues = any(
            i.get("severity") in SEVERITY_REVIEW_REQUIRED for i in issues if isinstance(i, dict)
        )

        # Preliminary check: Hard constraints
        is_safe_amount = total_amount < self.amount_threshold
        is_safe_severity = not has_high_risk_issues
        has_suggestions = len(suggested_updates) > 0

        if not (is_safe_amount and is_safe_severity and has_suggestions):
            reason = "Nên để human review: "
            if not is_safe_amount:
                reason += (
                    f"Số tiền {total_amount:,.0f} >= "
                    f"ngưỡng tự động {self.amount_threshold:,.0f}. "
                )
            if not is_safe_severity:
                reason += "Tồn tại cảnh báo mức Nghiêm trọng/Cao/Trung bình. "
            if not has_suggestions:
                reason += "Không có đề xuất nào để xác thực. "

            logger.info("[Agent Review] Hard constraints failed, escalating", reason=reason)
            return self._escalate(
                result_key,
                agent_result,
                stage,
                confidence,
                REASON_HARD_CONSTRAINTS_FAILED,
                reason,
            )

        # WHY: 2. Confidence & Cross-Verification
        # If confident, call the VerifierAgent to double-check.
        if confidence >= self.confidence_threshold:
            logger.info("[Agent Review] High confidence, starting cross-verification", stage=stage)

            # Call the Verifier Agent
            verifier_state = await self.verifier_agent(state)
            verifier_result = verifier_state.get("verifier_result") or {}

            # WHY: Even if verdict is 'pass', any found contradiction should trigger human eyes.
            has_contradictions = len(verifier_result.get("contradictions", [])) > 0

            if verifier_result.get("verdict") == "pass" and not has_contradictions:
                logger.info("[Agent Review] Cross-verification passed", stage=stage)
                return self._auto_approve(
                    result_key, agent_result, stage, confidence, len(suggested_updates)
                )
            else:
                reason = verifier_result.get("reason")
                reason_code = REASON_VERIFIER_FAILED
                if has_contradictions:
                    reason = f"Phát hiện mâu thuẫn bởi bộ xác thực: {verifier_result.get('contradictions')}"
                    reason_code = REASON_VERIFIER_CONTRADICTIONS

                logger.info(
                    "[Agent Review] Cross-verification failed or has contradictions",
                    stage=stage,
                    reason=reason,
                )
                return self._escalate(
                    result_key,
                    agent_result,
                    stage,
                    confidence,
                    reason_code,
                    f"Rủi ro từ bộ xác thực: {reason}",
                )

        # Default fallback for low confidence
        return self._escalate(
            result_key,
            agent_result,
            stage,
            confidence,
            REASON_LOW_CONFIDENCE,
            f"Độ tin cậy ban đầu thấp ({confidence})",
        )

    @staticmethod
    def _parse_claim_amount(value: Any) -> float:
        """Normalize OCR-extracted claim amount for threshold comparison."""
        if isinstance(value, int | float):
            return float(value)

        if isinstance(value, str):
            try:
                return float(value.replace(",", "").replace(".", ""))
            except ValueError:
                return float("inf")

        return 0.0

    def _auto_approve(
        self,
        result_key: str,
        agent_result: dict[str, Any],
        stage: str,
        confidence: float,
        num_suggestions: int,
    ) -> dict[str, Any]:
        """Mark agent result as auto-approved and return updated state.

        Args:
            result_key: State key for the agent result (e.g. 'agent_1_result').
            agent_result: The original agent result dict.
            stage: Current workflow stage ('completeness' or 'quality').
            confidence: Agent's confidence score.
            num_suggestions: Number of suggested updates applied.

        Returns:
            State update dict with auto-reviewed result and history entry.
        """
        updated_result = {**agent_result, "is_auto_reviewed": True}
        return {
            result_key: updated_result,
            "current_step": f"agent_reviewed_{stage}",
            "active_stage": STAGE_QUALITY if stage == STAGE_COMPLETENESS else STAGE_NONE,
            "review_stage": STAGE_NONE,
            "workflow_status": STATUS_RUNNING,
            "history": [
                {
                    "step": "agent_review",
                    "stage": stage,
                    "auto_reviewed": True,
                    "confidence": confidence,
                    "num_suggestions": num_suggestions,
                }
            ],
        }

    def _escalate(
        self,
        result_key: str,
        agent_result: dict[str, Any],
        stage: str,
        confidence: float,
        reason_code: str,
        reason: str,
    ) -> dict[str, Any]:
        """Escalate to human review with a detailed reason.

        Args:
            result_key: State key for the agent result (e.g. 'agent_1_result').
            agent_result: The original agent result dict.
            stage: Current workflow stage ('completeness' or 'quality').
            confidence: Agent's confidence score at the time of escalation.
            reason_code: Machine-readable reason for tests, metrics, and routing.
            reason: Human-readable explanation of why escalation is required.

        Returns:
            State update dict that triggers human review.
        """
        # WHY: Explicitly set is_auto_reviewed to False to ensure the router
        # correctly directs to human_review, even if the LLM hallucinated True.
        updated_result = {**agent_result, "is_auto_reviewed": False}

        return {
            result_key: updated_result,
            "current_step": f"agent_review_escalated_{stage}",
            "active_stage": STAGE_NONE,
            "review_stage": stage,
            "workflow_status": STATUS_WAITING_HUMAN,
            "pending_human_review": True,
            "history": [
                {
                    "step": "agent_review",
                    "stage": stage,
                    "auto_reviewed": False,
                    "confidence": confidence,
                    "escalation_reason_code": reason_code,
                    "escalation_reason": reason,
                }
            ],
        }

    @staticmethod
    def _review_stage(state: GraphState) -> str:
        explicit_stage = state.get("review_stage")
        if explicit_stage and explicit_stage != STAGE_NONE:
            return explicit_stage

        current_step = state.get("current_step", "")
        if STAGE_COMPLETENESS in current_step:
            return STAGE_COMPLETENESS
        return STAGE_QUALITY
