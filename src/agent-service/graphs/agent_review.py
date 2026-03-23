"""Agent Review Node for automated issue resolution.

This module implements the AgentReviewNode which acts as an automated
verification layer. When an assessment agent returns `accept_with_edit`,
the workflow routes here first. The VerifierAgent attempts to resolve
minor issues using available tools. If confident (score > 0.9) and no
critical/high issues remain, it marks the result as auto-reviewed and
the workflow proceeds without human intervention.
"""

import structlog
from typing import Any, Dict

from config import settings
from graphs.state import GraphState
from agents.factory import VerifierAgentFactory

logger = structlog.get_logger()


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

    async def run(self, state: GraphState) -> Dict[str, Any]:
        """Execute the agent review node.

        Examines the current agent result, checks confidence and issue
        severity, and decides whether to auto-approve or escalate to
        human review.

        Args:
            state: Current graph state.

        Returns:
            Dictionary with updated agent result and history.
        """
        current_step = state.get("current_step", "")

        # WHY: Determine which agent result to review based on the stage.
        if "completeness" in current_step:
            agent_result = state.get("agent_1_result") or {}
            result_key = "agent_1_result"
            stage = "completeness"
        else:
            agent_result = state.get("agent_2_result") or {}
            result_key = "agent_2_result"
            stage = "quality"

        confidence = agent_result.get("confidence_score", 0.0)
        issues = agent_result.get("issues", []) or []
        suggested_updates = agent_result.get("suggested_updates", []) or []

        # WHY: 1. Hard Constraints Check
        evidence = agent_result.get("evidence") or {}
        total_amount = evidence.get("total_claim_amount") or 0

        # WHY: OCR may extract amounts as strings like "5,000,000" or "5.000.000".
        # We must normalise to a numeric type for comparison.
        if isinstance(total_amount, str):
            try:
                total_amount = float(total_amount.replace(",", "").replace(".", ""))
            except (ValueError, AttributeError):
                # WHY: Unparseable amount is treated as high-risk.
                total_amount = float("inf")

        has_high_risk_issues = any(
            i.get("severity") in ("critical", "high", "medium")
            for i in issues
            if isinstance(i, dict)
        )

        # Preliminary check: Hard constraints
        is_safe_amount = total_amount < self.amount_threshold
        is_safe_severity = not has_high_risk_issues
        has_suggestions = len(suggested_updates) > 0

        if not (is_safe_amount and is_safe_severity and has_suggestions):
            reason = "Vi phạm ràng buộc cứng: "
            if not is_safe_amount:
                reason += f"Số tiền {total_amount:,.0f} >= ngưỡng {self.amount_threshold:,.0f}. "
            if not is_safe_severity:
                reason += "Tồn tại cảnh báo mức Nghiêm trọng/Cao/Trung bình. "
            if not has_suggestions:
                reason += "Không có đề xuất nào để xác thực. "

            logger.info("[Agent Review] Hard constraints failed, escalating", reason=reason)
            return self._escalate(result_key, agent_result, stage, confidence, reason)

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
                if has_contradictions:
                    reason = (
                        f"Phát hiện mâu thuẫn bởi bộ xác thực: {verifier_result.get('contradictions')}"
                    )

                logger.info(
                    "[Agent Review] Cross-verification failed or has contradictions",
                    stage=stage,
                    reason=reason,
                )
                return self._escalate(result_key, agent_result, stage, confidence, f"Rủi ro từ bộ xác thực: {reason}")

        # Default fallback for low confidence
        return self._escalate(result_key, agent_result, stage, confidence, f"Độ tin cậy ban đầu thấp ({confidence})")

    def _auto_approve(
        self,
        result_key: str,
        agent_result: Dict[str, Any],
        stage: str,
        confidence: float,
        num_suggestions: int,
    ) -> Dict[str, Any]:
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
        self, result_key: str, agent_result: Dict[str, Any], stage: str, confidence: float, reason: str
    ) -> Dict[str, Any]:
        """Escalate to human review with a detailed reason.

        Args:
            result_key: State key for the agent result (e.g. 'agent_1_result').
            agent_result: The original agent result dict.
            stage: Current workflow stage ('completeness' or 'quality').
            confidence: Agent's confidence score at the time of escalation.
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
            "pending_human_review": True,
            "history": [
                {
                    "step": "agent_review",
                    "stage": stage,
                    "auto_reviewed": False,
                    "confidence": confidence,
                    "escalation_reason": reason,
                }
            ],
        }
