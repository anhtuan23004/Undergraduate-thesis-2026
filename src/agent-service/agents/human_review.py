"""Human Review Node for multi-agent workflow.

This module implements the HumanReviewNode which simulates human review
decisions based on confidence scores and claim complexity.
"""

from typing import Any, Dict

from core.state import GraphState


class HumanReviewNode:
    """Node for simulating human review in the workflow.

    This node represents a human-in-the-loop review step where a human
    reviewer evaluates the claim based on agent outputs and makes a decision.

    In production, this would interface with an actual human review system.
    For simulation, it makes decisions based on confidence thresholds.

    Decision thresholds:
    - confidence > 0.8: Auto-approve (human agrees with agents)
    - confidence < 0.3: Auto-reject (human disagrees with agents)
    - 0.3 <= confidence <= 0.8: Edit/Review (human needs to examine)
    """

    # Decision thresholds
    APPROVE_THRESHOLD = 0.8
    REJECT_THRESHOLD = 0.3

    def __init__(self) -> None:
        """Initialize the HumanReviewNode."""
        pass

    async def run(self, state: GraphState) -> Dict[str, Any]:
        """Execute the human review simulation.

        Args:
            state: Current graph state containing agent_1_result and agent_2_result

        Returns:
            Dictionary containing human_review_result, current_step, and history updates
        """
        try:
            agent_1_result = state.get("agent_1_result", {})
            agent_2_result = state.get("agent_2_result", {})

            # Calculate confidence based on agent results
            confidence = self._calculate_confidence(agent_1_result, agent_2_result)

            # Determine decision based on confidence
            if confidence > self.APPROVE_THRESHOLD:
                decision = "approve"
                reason = "High confidence in agent validations - no human intervention needed"
            elif confidence < self.REJECT_THRESHOLD:
                decision = "reject"
                reason = "Low confidence in agent validations - claim rejected pending review"
            else:
                decision = "edit"
                reason = "Medium confidence - claim requires manual human review"

            # Build issues list from agent results
            issues = []

            # Add issues from agent 1
            if agent_1_result:
                for issue in agent_1_result.get("issues", []):
                    issues.append({
                        "severity": issue.get("severity", "medium"),
                        "message": issue.get("message", ""),
                        "field": issue.get("field", ""),
                        "source": "agent_1"
                    })

            # Add issues from agent 2
            if agent_2_result:
                for issue in agent_2_result.get("issues", []):
                    issues.append({
                        "severity": issue.get("severity", "medium"),
                        "message": issue.get("message", ""),
                        "field": issue.get("field", ""),
                        "source": "agent_2"
                    })

            # Determine validity based on decision
            valid = decision == "approve"

            human_review_result = {
                "valid": valid,
                "decision": decision,
                "confidence": round(confidence, 2),
                "reason": reason,
                "issues": issues,
                "reviewed_by": "human_reviewer_simulated",
                "agent_1_valid": agent_1_result.get("valid", False) if agent_1_result else False,
                "agent_2_valid": agent_2_result.get("valid", False) if agent_2_result else False
            }

            return {
                "human_review_result": human_review_result,
                "current_step": "human_review_complete",
                "history": [{
                    "step": "human_review",
                    "decision": decision,
                    "confidence": round(confidence, 2),
                    "valid": valid
                }]
            }

        except Exception as e:
            return {
                "human_review_result": {
                    "valid": False,
                    "decision": "reject",
                    "confidence": 0.0,
                    "reason": f"Human review failed: {str(e)}",
                    "issues": [{
                        "severity": "critical",
                        "message": f"Human review error: {str(e)}",
                        "field": "human_review"
                    }],
                    "reviewed_by": "error"
                },
                "current_step": "human_review_error",
                "history": [{
                    "step": "human_review",
                    "error": str(e)
                }],
                "error": str(e)
            }

    def _calculate_confidence(
        self,
        agent_1_result: Dict[str, Any],
        agent_2_result: Dict[str, Any]
    ) -> float:
        """Calculate confidence score based on agent results.

        Args:
            agent_1_result: Result from completeness agent
            agent_2_result: Result from quality agent

        Returns:
            Confidence score between 0.0 and 1.0
        """
        scores = []

        # Agent 1 contribution (completeness)
        if agent_1_result:
            if agent_1_result.get("valid", False):
                scores.append(0.9)
            else:
                # Reduce score based on issue count
                issue_count = len(agent_1_result.get("issues", []))
                high_issues = sum(
                    1 for i in agent_1_result.get("issues", [])
                    if i.get("severity") in ["high", "critical"]
                )
                if high_issues > 0:
                    scores.append(0.3)
                elif issue_count > 3:
                    scores.append(0.5)
                else:
                    scores.append(0.7)
        else:
            scores.append(0.5)  # Neutral if no result

        # Agent 2 contribution (quality)
        if agent_2_result:
            if agent_2_result.get("valid", False):
                scores.append(0.9)
            else:
                # Reduce score based on severity
                severity_score = agent_2_result.get("severity_score", 0.5)
                critical_count = sum(
                    1 for i in agent_2_result.get("issues", [])
                    if i.get("severity") == "critical"
                )
                if critical_count > 0:
                    scores.append(0.2)
                else:
                    scores.append(max(0.3, 1.0 - severity_score))
        else:
            scores.append(0.5)  # Neutral if no result

        # Average the scores
        if scores:
            return sum(scores) / len(scores)
        return 0.5
