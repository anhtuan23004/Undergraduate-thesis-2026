"""Custom Langflow component for checking insurance policy coverage."""
from langflow.custom import Component
from langflow.io import MessageTextInput, Output
from langflow.schema import Data
import httpx


class PolicyCheckerComponent(Component):
    """Check policy coverage using the RAG service."""

    display_name = "Policy Checker"
    description = "Query policy coverage information from the RAG service"
    icon = "shield"
    name = "PolicyChecker"

    inputs = [
        MessageTextInput(
            name="policy_number",
            display_name="Policy Number",
            info="The insurance policy number to check",
            value="POL-001",
        ),
        MessageTextInput(
            name="query",
            display_name="Query",
            info="What to ask about the policy (e.g., 'coverage for pneumonia')",
            value="What is the coverage for this diagnosis?",
        ),
        MessageTextInput(
            name="rag_service_url",
            display_name="RAG Service URL",
            info="URL of the RAG service",
            value="http://rag-service:8000",
        ),
    ]

    outputs = [
        Output(display_name="Policy Data", name="policy_data", method="check_policy"),
        Output(display_name="Coverage Info", name="coverage_info", method="get_coverage"),
    ]

    async def check_policy(self) -> Data:
        """Query policy information from RAG service."""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.rag_service_url}/api/v1/rag/query",
                    json={
                        "query": self.query,
                        "policy_number": self.policy_number,
                    },
                )
                response.raise_for_status()
                data = response.json()

                return Data(data={
                    "policy_number": self.policy_number,
                    "query": self.query,
                    "response": data.get("answer", "No answer found"),
                    "sources": data.get("sources", []),
                    "status": "success",
                })

        except Exception as e:
            return Data(data={
                "policy_number": self.policy_number,
                "query": self.query,
                "error": str(e),
                "status": "error",
            })

    async def get_coverage(self) -> Data:
        """Extract coverage information from policy check."""
        result = await self.check_policy()

        if result.data.get("status") == "error":
            return result

        # Parse coverage info from response
        response_text = result.data.get("response", "")

        # Simple extraction logic (can be enhanced with LLM)
        coverage_info = {
            "policy_number": self.policy_number,
            "full_response": response_text,
            "has_coverage": "covered" in response_text.lower() or "eligible" in response_text.lower(),
            "has_exclusion": "exclusion" in response_text.lower() or "not covered" in response_text.lower(),
        }

        return Data(data=coverage_info)
