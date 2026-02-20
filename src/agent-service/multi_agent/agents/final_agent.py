"""Final Agent for multi-agent workflow.

This module implements the FinalAgent which aggregates all validation results
and makes the final decision on claim processing.
"""

from typing import Any, Dict

from core.llm.client import LLMClient
from multi_agent.config.loader import ConfigLoader
from multi_agent.core.state import GraphState
from multi_agent.tools import AggregateIssuesTool


class FinalAgent:
    """Agent for making final claim processing decisions.

    This agent performs the final stage of claim processing:
    1. Aggregates all issues from previous agents
    2. Applies severity-weighted analysis
    3. Generates final recommendation
    4. Produces final output

    Attributes:
        config: Agent configuration loaded from YAML
        aggregate_tool: Tool for aggregating issues from all agents
        llm: LLM client for generating final analysis
    """

    def __init__(self) -> None:
        """Initialize the FinalAgent."""
        self.config = ConfigLoader().load_agent("final_agent")
        self.aggregate_tool = AggregateIssuesTool()
        self.llm = LLMClient()

    async def run(self, state: GraphState) -> Dict[str, Any]:
        """Execute the final agent.

        Args:
            state: Current graph state containing all agent results

        Returns:
            Dictionary containing final_result, current_step, should_continue=False
        """
        try:
            agent_1_result = state.get("agent_1_result", {})
            agent_2_result = state.get("agent_2_result", {})
            human_review_result = state.get("human_review_result", {})
            extracted_docs = state.get("extracted_documents", {})

            # Prepare results for aggregation
            agg_agent_1 = self._prepare_agent_result(agent_1_result)
            agg_agent_2 = self._prepare_agent_result(agent_2_result)
            agg_human = self._prepare_agent_result(human_review_result)

            # Aggregate all issues
            aggregate_result = await self.aggregate_tool.execute(
                agent_1_result=agg_agent_1,
                agent_2_result=agg_agent_2,
                human_review_result=agg_human
            )

            # Get recommendation from aggregation
            recommendation = aggregate_result.get("recommendation", "review")
            weighted_score = aggregate_result.get("weighted_score", 0)

            # Map recommendation to final decision
            decision_map = {
                "approve": "APPROVED",
                "reject": "REJECTED",
                "review": "PENDING_REVIEW"
            }
            final_decision = decision_map.get(recommendation, "PENDING_REVIEW")

            # Calculate confidence based on aggregation
            confidence = self._calculate_final_confidence(
                agent_1_result,
                agent_2_result,
                human_review_result,
                weighted_score
            )

            # Generate final analysis using LLM
            prompt = self._build_final_prompt(
                extracted_docs,
                agent_1_result,
                agent_2_result,
                human_review_result,
                aggregate_result,
                final_decision
            )

            analysis = await self.llm.generate(
                prompt=prompt,
                system_prompt="You are a senior insurance claims adjudicator making final decisions.",
                temperature=0.2
            )

            # Build final result
            final_result = {
                "decision": final_decision,
                "confidence": round(confidence, 2),
                "recommendation_reason": aggregate_result.get("recommendation_reason", ""),
                "weighted_score": weighted_score,
                "aggregated_issues": aggregate_result.get("aggregated_issues", []),
                "issue_summary": aggregate_result.get("summary", {}),
                "claim_data": {
                    "patient_name": extracted_docs.get("patient_name", ""),
                    "policy_number": extracted_docs.get("policy_number", ""),
                    "claim_amount": extracted_docs.get("total_amount"),
                    "service_date": extracted_docs.get("service_date"),
                    "provider": extracted_docs.get("provider_name", ""),
                    "diagnosis_codes": extracted_docs.get("diagnosis_codes", []),
                    "benefit_category": agent_1_result.get("benefit_category") if agent_1_result else None
                },
                "agent_results": {
                    "completeness_valid": agent_1_result.get("valid", False) if agent_1_result else False,
                    "quality_valid": agent_2_result.get("valid", False) if agent_2_result else False,
                    "human_decision": human_review_result.get("decision") if human_review_result else None
                },
                "final_analysis": analysis
            }

            return {
                "final_result": final_result,
                "current_step": "final_decision_complete",
                "should_continue": False,
                "history": [{
                    "step": "final_agent",
                    "decision": final_decision,
                    "confidence": round(confidence, 2),
                    "weighted_score": weighted_score
                }]
            }

        except Exception as e:
            return {
                "final_result": {
                    "decision": "ERROR",
                    "confidence": 0.0,
                    "error": str(e),
                    "recommendation_reason": f"Final agent failed: {str(e)}"
                },
                "current_step": "final_decision_error",
                "should_continue": False,
                "history": [{
                    "step": "final_agent",
                    "error": str(e)
                }],
                "error": str(e)
            }

    def _prepare_agent_result(self, agent_result: Dict[str, Any]) -> Dict[str, Any]:
        """Prepare agent result for aggregation tool.

        Args:
            agent_result: Raw agent result from state

        Returns:
            Formatted result with issues and valid flag
        """
        if not agent_result:
            return {"valid": False, "issues": []}

        issues = agent_result.get("issues", [])
        valid = agent_result.get("valid", False)

        # Ensure all issues have required fields
        formatted_issues = []
        for issue in issues:
            formatted_issues.append({
                "severity": issue.get("severity", "medium"),
                "message": issue.get("message", "Unknown issue"),
                "field": issue.get("field", "unknown")
            })

        return {
            "valid": valid,
            "issues": formatted_issues
        }

    def _calculate_final_confidence(
        self,
        agent_1_result: Dict[str, Any],
        agent_2_result: Dict[str, Any],
        human_review_result: Dict[str, Any],
        weighted_score: float
    ) -> float:
        """Calculate final confidence score.

        Args:
            agent_1_result: Completeness agent result
            agent_2_result: Quality agent result
            human_review_result: Human review result
            weighted_score: Aggregated weighted score from issues

        Returns:
            Confidence score between 0.0 and 1.0
        """
        scores = []

        # Agent 1 confidence
        if agent_1_result:
            if agent_1_result.get("valid", False):
                scores.append(0.9)
            else:
                issue_count = len(agent_1_result.get("issues", []))
                scores.append(max(0.4, 1.0 - (issue_count * 0.1)))
        else:
            scores.append(0.5)

        # Agent 2 confidence
        if agent_2_result:
            if agent_2_result.get("valid", False):
                scores.append(0.9)
            else:
                severity = agent_2_result.get("severity_score", 0.5)
                scores.append(max(0.3, 1.0 - severity))
        else:
            scores.append(0.5)

        # Human review confidence
        if human_review_result:
            human_confidence = human_review_result.get("confidence", 0.5)
            decision = human_review_result.get("decision", "edit")
            if decision == "approve":
                scores.append(0.95)
            elif decision == "reject":
                scores.append(0.3)
            else:
                scores.append(human_confidence)
        else:
            scores.append(0.5)

        # Weighted score factor (lower score = higher confidence)
        score_factor = max(0.0, 1.0 - (weighted_score / 10.0))
        scores.append(score_factor)

        # Average all scores
        return sum(scores) / len(scores)

    def _build_final_prompt(
        self,
        extracted_docs: Dict[str, Any],
        agent_1_result: Dict[str, Any],
        agent_2_result: Dict[str, Any],
        human_review_result: Dict[str, Any],
        aggregate_result: Dict[str, Any],
        final_decision: str
    ) -> str:
        """Build prompt for final LLM analysis.

        Args:
            extracted_docs: Extracted document data
            agent_1_result: Completeness agent result
            agent_2_result: Quality agent result
            human_review_result: Human review result
            aggregate_result: Issue aggregation result
            final_decision: Final decision string

        Returns:
            Formatted prompt string
        """
        lines = [
            "Provide a final analysis for this insurance claim:",
            "",
            f"## Final Decision: {final_decision}",
            "",
            "## Claim Information:",
            f"- Patient: {extracted_docs.get('patient_name', 'Unknown')}",
            f"- Policy: {extracted_docs.get('policy_number', 'Unknown')}",
            f"- Amount: {extracted_docs.get('total_amount', 'Unknown')}",
            f"- Service Date: {extracted_docs.get('service_date', 'Unknown')}",
            "",
            "## Agent Results Summary:",
            f"- Completeness Check: {'PASSED' if agent_1_result and agent_1_result.get('valid') else 'FAILED'}",
            f"- Quality Check: {'PASSED' if agent_2_result and agent_2_result.get('valid') else 'FAILED'}",
            f"- Human Review: {human_review_result.get('decision', 'N/A').upper() if human_review_result else 'N/A'}",
            "",
            "## Issue Summary:",
            str(aggregate_result.get('summary', {})),
            "",
            "## Aggregated Issues:",
        ]

        for issue in aggregate_result.get("aggregated_issues", [])[:10]:
            lines.append(f"- [{issue.get('severity', 'unknown').upper()}] {issue.get('message', '')}")

        lines.extend([
            "",
            "## Instructions:",
            "Provide a concise final analysis explaining the decision.",
            "Include key findings and any recommendations for the claimant."
        ])

        return "\n".join(lines)
