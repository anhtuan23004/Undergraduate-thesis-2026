"""Quality Agent for multi-agent workflow.

This module implements the QualityAgent which performs quality validation
including consistency checks, diagnosis validation, exclusion checks, and
medication validation.
"""

from typing import Any, Dict

from core.llm.client import LLMClient
from multi_agent.config.loader import ConfigLoader
from multi_agent.core.state import GraphState
from multi_agent.tools import (
    ValidateConsistencyTool,
    ValidateDiagnosisTool,
    CheckExclusionTool,
    ValidateMedicationTool,
)


class QualityAgent:
    """Agent for validating claim quality and consistency.

    This agent performs the second stage of claim processing:
    1. Validates consistency across documents
    2. Validates diagnosis codes and coverage
    3. Checks for policy exclusions
    4. Validates medications

    Attributes:
        config: Agent configuration loaded from YAML
        instructions: Agent instructions loaded from Markdown
        llm: LLM client for generating responses
        tools: List of tools available to this agent
    """

    def __init__(self) -> None:
        """Initialize the QualityAgent."""
        self.config = ConfigLoader().load_agent("quality_check_agent")
        self.instructions = ConfigLoader().load_instructions("quality_agent")
        self.llm = LLMClient()
        self.tools = [
            ValidateConsistencyTool(),
            ValidateDiagnosisTool(),
            CheckExclusionTool(),
            ValidateMedicationTool(),
        ]

    async def run(self, state: GraphState) -> Dict[str, Any]:
        """Execute the quality check agent.

        Args:
            state: Current graph state containing extracted_documents and agent_1_result

        Returns:
            Dictionary containing agent_2_result, current_step, and history updates
        """
        try:
            extracted_docs = state.get("extracted_documents", {})
            agent_1_result = state.get("agent_1_result", {})

            # Get patient and claim info
            patient_name = extracted_docs.get("patient_name", "")
            patient_id = extracted_docs.get("patient_id", "")
            policy_number = extracted_docs.get("policy_number", "")
            claim_amount = extracted_docs.get("total_amount")
            service_date = extracted_docs.get("service_date")
            provider_name = extracted_docs.get("provider_name", "")
            diagnosis_codes = extracted_docs.get("diagnosis_codes", [])
            medications = extracted_docs.get("medications", [])
            documents = extracted_docs.get("documents", [])

            issues = []

            # Step 1: Validate consistency
            consistency_result = await ValidateConsistencyTool().execute(
                patient_name=patient_name,
                patient_id=patient_id,
                policy_number=policy_number,
                claim_amount=claim_amount,
                service_date=service_date,
                provider_name=provider_name,
                documents=documents
            )

            if consistency_result.get("success"):
                if not consistency_result.get("valid", True):
                    for issue in consistency_result.get("issues", []):
                        if issue.get("severity") in ["high", "critical"]:
                            issues.append({
                                "severity": issue["severity"],
                                "message": issue.get("message", "Consistency error"),
                                "field": issue.get("field", "consistency")
                            })
                # Add warnings
                for issue in consistency_result.get("issues", []):
                    if issue.get("severity") == "low":
                        issues.append({
                            "severity": "low",
                            "message": issue.get("message", ""),
                            "field": issue.get("field", "consistency")
                        })

            # Step 2: Validate diagnosis
            diagnosis_result = await ValidateDiagnosisTool().execute(
                diagnosis_codes=diagnosis_codes,
                policy_number=policy_number
            )

            if diagnosis_result.get("success"):
                if not diagnosis_result.get("valid", True):
                    for issue in diagnosis_result.get("issues", []):
                        issues.append({
                            "severity": issue.get("severity", "medium"),
                            "message": issue.get("message", "Diagnosis validation error"),
                            "field": issue.get("field", "diagnosis")
                        })
            else:
                issues.append({
                    "severity": "medium",
                    "message": f"Diagnosis validation failed: {diagnosis_result.get('error', 'Unknown error')}",
                    "field": "diagnosis"
                })

            # Step 3: Check exclusions
            exclusion_result = await CheckExclusionTool().execute(
                diagnosis_codes=diagnosis_codes,
                procedures=extracted_docs.get("procedures", []),
                policy_number=policy_number
            )

            if exclusion_result.get("success"):
                exclusions = exclusion_result.get("exclusions_found", [])
                for exclusion in exclusions:
                    issues.append({
                        "severity": "critical",
                        "message": f"Policy exclusion found: {exclusion.get('description', 'Unknown exclusion')}",
                        "field": exclusion.get("type", "exclusion")
                    })
            else:
                issues.append({
                    "severity": "low",
                    "message": f"Exclusion check could not be completed: {exclusion_result.get('error', 'Unknown error')}",
                    "field": "exclusion"
                })

            # Step 4: Validate medications
            medication_result = await ValidateMedicationTool().execute(
                medications=medications,
                diagnosis_codes=diagnosis_codes,
                policy_number=policy_number
            )

            if medication_result.get("success"):
                if not medication_result.get("valid", True):
                    for issue in medication_result.get("issues", []):
                        issues.append({
                            "severity": issue.get("severity", "medium"),
                            "message": issue.get("message", "Medication validation error"),
                            "field": issue.get("field", "medication")
                        })
            else:
                issues.append({
                    "severity": "low",
                    "message": f"Medication validation could not be completed: {medication_result.get('error', 'Unknown error')}",
                    "field": "medication"
                })

            # Determine overall validity
            critical_count = sum(1 for i in issues if i.get("severity") == "critical")
            high_count = sum(1 for i in issues if i.get("severity") == "high")
            valid = critical_count == 0 and high_count == 0

            # Use LLM to analyze and summarize
            prompt = self._build_analysis_prompt(
                extracted_docs,
                consistency_result,
                diagnosis_result,
                exclusion_result,
                medication_result,
                issues
            )

            analysis = await self.llm.generate(
                prompt=prompt,
                system_prompt=self.instructions,
                temperature=0.3
            )

            agent_result = {
                "valid": valid,
                "issues": issues,
                "consistency_check": consistency_result if consistency_result.get("success") else None,
                "diagnosis_check": diagnosis_result if diagnosis_result.get("success") else None,
                "exclusion_check": exclusion_result if exclusion_result.get("success") else None,
                "medication_check": medication_result if medication_result.get("success") else None,
                "analysis": analysis,
                "severity_score": self._calculate_severity_score(issues)
            }

            return {
                "agent_2_result": agent_result,
                "current_step": "quality_check_complete",
                "history": [{
                    "step": "quality_agent",
                    "valid": valid,
                    "issue_count": len(issues),
                    "critical_count": critical_count,
                    "high_count": high_count
                }]
            }

        except Exception as e:
            return {
                "agent_2_result": {
                    "valid": False,
                    "issues": [{
                        "severity": "critical",
                        "message": f"Quality agent failed: {str(e)}",
                        "field": "agent_error"
                    }],
                    "error": str(e)
                },
                "current_step": "quality_check_error",
                "history": [{
                    "step": "quality_agent",
                    "error": str(e)
                }],
                "error": str(e)
            }

    def _calculate_severity_score(self, issues: list) -> float:
        """Calculate overall severity score from issues.

        Args:
            issues: List of issue dictionaries with severity

        Returns:
            Severity score from 0.0 (clean) to 1.0 (critical)
        """
        if not issues:
            return 0.0

        weights = {"critical": 1.0, "high": 0.7, "medium": 0.4, "low": 0.1}
        total = sum(weights.get(i.get("severity", "medium"), 0.4) for i in issues)
        return min(1.0, total / 5.0)

    def _build_analysis_prompt(
        self,
        extracted_docs: Dict[str, Any],
        consistency_result: Dict[str, Any],
        diagnosis_result: Dict[str, Any],
        exclusion_result: Dict[str, Any],
        medication_result: Dict[str, Any],
        issues: list
    ) -> str:
        """Build prompt for LLM analysis.

        Args:
            extracted_docs: Extracted document data
            consistency_result: Consistency validation result
            diagnosis_result: Diagnosis validation result
            exclusion_result: Exclusion check result
            medication_result: Medication validation result
            issues: List of identified issues

        Returns:
            Formatted prompt string
        """
        lines = [
            "Analyze the following claim data for quality and consistency:",
            "",
            "## Extracted Documents:",
            str(extracted_docs)[:800],
            "",
            "## Consistency Check:",
            str(consistency_result)[:400],
            "",
            "## Diagnosis Validation:",
            str(diagnosis_result)[:400],
            "",
            "## Exclusion Check:",
            str(exclusion_result)[:400],
            "",
            "## Medication Validation:",
            str(medication_result)[:400],
            "",
            "## Identified Issues:",
        ]

        for issue in issues:
            lines.append(f"- [{issue['severity'].upper()}] {issue['message']}")

        lines.extend([
            "",
            "Provide a concise analysis of the claim's quality and any concerns."
        ])

        return "\n".join(lines)
