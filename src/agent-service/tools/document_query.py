"""Document query tool."""
from typing import Any, Dict, List

from tools.base import BaseTool


# Mock document data
MOCK_DOCUMENT_DATA = {
    "patient": "Nguyễn Văn A",
    "patient_id": "123456789",
    "dob": "1980-05-15",
    "hospital": "Bệnh viện Chợ Rẫy",
    "admission_date": "2025-01-10",
    "discharge_date": "2025-01-15",
    "diagnosis": "Viêm phổi",
    "diagnosis_codes": ["J18.9"],
    "procedures": ["X-quang ngực", "Kháng sinh IV"],
    "medications": ["Ceftriaxone", "Azithromycin"],
    "total_amount": 15_500_000,
    "doctor": "BS. Trần Văn B"
}

REQUIRED_FIELDS = ["patient", "hospital", "total_amount"]


class DocumentQueryTool(BaseTool):
    """Tool for querying extracted document fields."""

    name = "document_query"
    description = "Query and verify information from extracted claim documents"

    async def arun(
        self,
        claim_id: str,
        fields: List[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Query document fields.

        Args:
            claim_id: Claim identifier
            fields: List of fields to query

        Returns:
            Document field values
        """
        # TODO: Connect to MongoDB for actual document lookup
        # For now, return mock data

        result = {k: v for k, v in MOCK_DOCUMENT_DATA.items() if not fields or k in fields}
        missing = [f for f in REQUIRED_FIELDS if f not in result or not result[f]]

        return {
            "status": "success" if not missing else "incomplete",
            "claim_id": claim_id,
            "fields": result,
            "missing_fields": missing,
            "summary": f"Retrieved {len(result)} fields" + (f", missing: {', '.join(missing)}" if missing else "")
        }
