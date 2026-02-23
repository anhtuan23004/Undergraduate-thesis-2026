"""Completeness Agent for multi-agent workflow.

This module implements the CompletenessAgent which performs initial document
validation including document extraction, benefit classification, and required
document verification.
"""

from typing import Any, Dict, Optional

from core.llm.client import LLMClient
from config.loader import ConfigLoader
from core.state import GraphState
from tools import (
    ExtractDocumentsTool,
    ClassifyBenefitTool,
    CheckRequiredDocumentsTool,
)


class CompletenessAgent:
    """Agent for checking document completeness and initial validation.

    This agent performs the first stage of claim processing:
    1. Extracts documents from input files
    2. Classifies the benefit type
    3. Verifies all required documents are present

    Attributes:
        config: Agent configuration loaded from YAML
        instructions: Agent instructions loaded from Markdown
        llm: LLM client for generating responses
        tools: List of tools available to this agent
    """

    def __init__(self) -> None:
        """Initialize the CompletenessAgent."""
        self.config = ConfigLoader().load_agent("completeness_check_agent")
        self.instructions = ConfigLoader().load_instructions("completeness_agent")
        self.llm = LLMClient()
        self.tools = [
            ExtractDocumentsTool(),
            ClassifyBenefitTool(),
            CheckRequiredDocumentsTool(),
        ]

    async def run(self, state: GraphState) -> Dict[str, Any]:
        """Execute the completeness check agent.

        Args:
            state: Current graph state containing input_file and extracted_documents

        Returns:
            Dictionary containing agent_1_result, current_step, and history updates
        """
        try:
            # Step 1: Extract documents if not already extracted
            extracted_docs = state.get("extracted_documents", {})
            if not extracted_docs and state.get("input_file"):
                extract_tool = ExtractDocumentsTool()
                extract_result = await extract_tool.execute(
                    extraction_type="document",
                    file_path=state["input_file"],
                    prompt="Extract all claim documents, patient information, diagnosis, and medical procedures"
                )
                if extract_result.get("success"):
                    extracted_docs = extract_result.get("data", {})

            # Step 2: Classify benefit type
            classify_tool = ClassifyBenefitTool()
            diagnosis = extracted_docs.get("diagnosis", "")
            diagnosis_codes = extracted_docs.get("diagnosis_codes", [])
            procedures = extracted_docs.get("procedures", [])
            medications = extracted_docs.get("medications", [])
            hospital_days = extracted_docs.get("hospital_stay_days")

            classify_result = await classify_tool.execute(
                diagnosis=diagnosis,
                diagnosis_codes=diagnosis_codes,
                procedures=procedures,
                medications=medications,
                hospital_stay_days=hospital_days,
                document_text=str(extracted_docs)
            )

            benefit_category = None
            if classify_result.get("success"):
                primary = classify_result.get("primary_category", {})
                benefit_category = primary.get("code") if primary else None

            # Step 3: Check required documents
            submitted_docs = extracted_docs.get("documents", [])
            claim_amount = extracted_docs.get("total_amount")

            required_result = await CheckRequiredDocumentsTool().execute(
                benefit_category=benefit_category or "outpatient",
                submitted_documents=submitted_docs,
                claim_amount=claim_amount,
                hospital_stay_days=hospital_days
            )

            # Build agent result
            issues = []
            valid = True

            # Add classification issues
            if not classify_result.get("success"):
                issues.append({
                    "severity": "medium",
                    "message": f"Benefit classification failed: {classify_result.get('message', 'Unknown error')}",
                    "field": "benefit_classification"
                })
                valid = False
            elif classify_result.get("confidence") == "low":
                issues.append({
                    "severity": "low",
                    "message": "Low confidence in benefit classification",
                    "field": "benefit_classification"
                })

            # Add document requirement issues
            if required_result.get("success"):
                if required_result.get("status") == "incomplete":
                    missing = required_result.get("mandatory_documents", {}).get("missing", [])
                    for doc in missing:
                        issues.append({
                            "severity": "high",
                            "message": f"Missing required document: {doc.get('name', doc.get('type', 'Unknown'))}",
                            "field": doc.get("type", "document")
                        })
                    valid = False

                # Add optional document warnings
                missing_optional = required_result.get("optional_documents", {}).get("missing", [])
                for doc in missing_optional[:3]:  # Limit to first 3
                    issues.append({
                        "severity": "low",
                        "message": f"Optional document not found: {doc.get('name', doc.get('type', 'Unknown'))}",
                        "field": doc.get("type", "document")
                    })
            else:
                issues.append({
                    "severity": "medium",
                    "message": f"Document check failed: {required_result.get('error', 'Unknown error')}",
                    "field": "document_check"
                })
                valid = False

            # Use LLM to analyze and summarize
            prompt = self._build_analysis_prompt(
                extracted_docs, classify_result, required_result, issues
            )

            analysis = await self.llm.generate(
                prompt=prompt,
                system_prompt=self.instructions,
                temperature=0.3
            )

            agent_result = {
                "valid": valid and len([i for i in issues if i["severity"] == "high"]) == 0,
                "issues": issues,
                "benefit_category": benefit_category,
                "classification": classify_result if classify_result.get("success") else None,
                "document_check": required_result if required_result.get("success") else None,
                "analysis": analysis,
                "extracted_data": extracted_docs
            }

            return {
                "agent_1_result": agent_result,
                "current_step": "completeness_check_complete",
                "history": [{
                    "step": "completeness_agent",
                    "valid": agent_result["valid"],
                    "issue_count": len(issues),
                    "benefit_category": benefit_category
                }]
            }

        except Exception as e:
            return {
                "agent_1_result": {
                    "valid": False,
                    "issues": [{
                        "severity": "critical",
                        "message": f"Completeness agent failed: {str(e)}",
                        "field": "agent_error"
                    }],
                    "error": str(e)
                },
                "current_step": "completeness_check_error",
                "history": [{
                    "step": "completeness_agent",
                    "error": str(e)
                }],
                "error": str(e)
            }

    def _build_analysis_prompt(
        self,
        extracted_docs: Dict[str, Any],
        classify_result: Dict[str, Any],
        required_result: Dict[str, Any],
        issues: list
    ) -> str:
        """Build prompt for LLM analysis.

        Args:
            extracted_docs: Extracted document data
            classify_result: Benefit classification result
            required_result: Required documents check result
            issues: List of identified issues

        Returns:
            Formatted prompt string
        """
        lines = [
            "Analyze the following claim data for completeness:",
            "",
            "## Extracted Documents:",
            str(extracted_docs)[:1000],
            "",
            "## Benefit Classification:",
            str(classify_result)[:500],
            "",
            "## Document Requirements:",
            str(required_result)[:500],
            "",
            "## Identified Issues:",
        ]

        for issue in issues:
            lines.append(f"- [{issue['severity'].upper()}] {issue['message']}")

        lines.extend([
            "",
            "Provide a concise analysis of the claim's completeness and any actions needed."
        ])

        return "\n".join(lines)
