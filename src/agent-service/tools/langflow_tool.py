"""Langflow tool wrapper for running exported flows.

This module provides a bridge between Langflow-exported Python flows
and the Agent Service's tool system.
"""
from typing import Dict, Any, Type
import structlog

from tools.base import BaseTool
from tools.langflow_flows import FraudDetectionFlow

logger = structlog.get_logger()


class LangflowTool(BaseTool):
    """Wrapper for Langflow-exported flows as Agent tools.

    This tool wraps a Langflow flow (exported as Python) and makes it
    callable by the ReAct agent. It handles:
    - Input/output formatting
    - Error handling
    - Logging

    Example:
        tool = LangflowTool(FraudDetectionFlow)
        result = await tool.arun(
            claim_id="CLM-001",
            amount=15000000,
            hospital="BV Cho Ray"
        )
    """

    def __init__(self, flow_class: Type, name: str = None):
        """Initialize the Langflow tool.

        Args:
            flow_class: The Langflow flow class to wrap
            name: Optional tool name (defaults to class name)
        """
        self.flow = flow_class()
        self.flow_class = flow_class
        self._name = name or flow_class.__name__

    @property
    def name(self) -> str:
        """Tool name."""
        return self._name

    @property
    def description(self) -> str:
        """Tool description."""
        return getattr(
            self.flow_class,
            "__doc__",
            f"Execute {self._name} workflow"
        )

    async def arun(self, **kwargs) -> Dict[str, Any]:
        """Execute the Langflow flow.

        Args:
            **kwargs: Input data for the flow

        Returns:
            Flow execution result
        """
        try:
            logger.info(
                "Running Langflow workflow",
                tool=self._name,
                inputs=list(kwargs.keys())
            )

            # Run the flow
            result = await self.flow.run(kwargs)

            logger.info(
                "Langflow workflow completed",
                tool=self._name,
                success=True
            )

            return {
                "tool": self._name,
                "status": "success",
                "result": result
            }

        except Exception as e:
            logger.error(
                "Langflow workflow failed",
                tool=self._name,
                error=str(e)
            )

            return {
                "tool": self._name,
                "status": "error",
                "error": str(e),
                "result": None
            }


class FraudDetectionTool(BaseTool):
    """Fraud detection tool using Langflow-exported flow.

    This tool performs fraud checks on insurance claims:
    - Amount threshold validation
    - Suspicious keyword detection
    - Diagnosis code risk assessment
    - Claim velocity tracking

    Example:
        result = await tool.arun(
            claim_id="CLM-001",
            amount=15000000,
            hospital="BV Cho Ray",
            diagnosis_codes=["J18.9"]
        )
    """

    def __init__(self):
        """Initialize fraud detection tool."""
        self.flow = FraudDetectionFlow()

    @property
    def name(self) -> str:
        return "fraud_detection"

    @property
    def description(self) -> str:
        return (
            "Analyze claim for fraud indicators. "
            "Checks amount, keywords, diagnosis codes, and claim frequency. "
            "Returns risk score and recommendation."
        )

    async def arun(
        self,
        claim_id: str,
        amount: float,
        hospital: str = None,
        diagnosis_codes: list = None,
        submission_date: str = None,
        description: str = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Run fraud detection on a claim.

        Args:
            claim_id: Unique claim identifier
            amount: Claim amount in VND
            hospital: Hospital name
            diagnosis_codes: List of ICD-10 codes
            submission_date: Submission date (ISO format)
            description: Optional claim description

        Returns:
            Fraud check results with risk_score, flags, and recommendation
        """
        claim_data = {
            "claim_id": claim_id,
            "amount": amount,
            "hospital": hospital,
            "diagnosis_codes": diagnosis_codes or [],
            "submission_date": submission_date,
            "description": description,
            **kwargs
        }

        try:
            result = await self.flow.run(claim_data)

            return {
                "tool": self.name,
                "status": "success",
                "summary": (
                    f"Risk Score: {result['risk_score']}, "
                    f"Flags: {len(result['flags'])}, "
                    f"Recommendation: {result['recommendation'][:50]}..."
                ),
                "result": result
            }

        except Exception as e:
            logger.error("Fraud detection failed", error=str(e))
            return {
                "tool": self.name,
                "status": "error",
                "error": str(e),
                "summary": "Fraud detection failed"
            }
