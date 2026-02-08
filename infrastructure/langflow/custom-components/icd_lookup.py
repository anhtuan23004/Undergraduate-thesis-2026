"""Custom Langflow component for ICD-10 diagnosis code lookup."""
from langflow.custom import Component
from langflow.io import MessageTextInput, Output
from langflow.schema import Data
import httpx


class ICDLookupComponent(Component):
    """Lookup ICD-10 diagnosis codes and validate coverage."""

    display_name = "ICD Lookup"
    description = "Validate ICD-10 codes and check diagnosis coverage"
    icon = "stethoscope"
    name = "ICDLookup"

    inputs = [
        MessageTextInput(
            name="diagnosis_codes",
            display_name="Diagnosis Codes",
            info="Comma-separated ICD-10 codes (e.g., 'J18.9,E11.9')",
            value="J18.9",
        ),
        MessageTextInput(
            name="agent_service_url",
            display_name="Agent Service URL",
            info="URL of the agent service for ICD validation",
            value="http://agent-service:8000",
        ),
    ]

    outputs = [
        Output(display_name="ICD Data", name="icd_data", method="lookup_codes"),
        Output(display_name="Validation", name="validation", method="validate_codes"),
    ]

    async def lookup_codes(self) -> Data:
        """Lookup ICD-10 code information."""
        codes = [c.strip() for c in self.diagnosis_codes.split(",") if c.strip()]

        # Mock ICD database (in production, this would call a real service)
        icd_database = {
            "J18.9": {
                "description": "Pneumonia, unspecified organism",
                "category": "Infectious diseases",
                "common": True,
            },
            "E11.9": {
                "description": "Type 2 diabetes mellitus without complications",
                "category": "Endocrine diseases",
                "common": True,
            },
            "I10": {
                "description": "Essential (primary) hypertension",
                "category": "Circulatory diseases",
                "common": True,
            },
        }

        results = []
        for code in codes:
            info = icd_database.get(code.upper(), {
                "description": "Unknown code",
                "category": "Unknown",
                "common": False,
            })
            results.append({
                "code": code.upper(),
                **info,
            })

        return Data(data={
            "codes": codes,
            "results": results,
            "total_codes": len(codes),
            "valid_codes": len([r for r in results if r["description"] != "Unknown code"]),
        })

    async def validate_codes(self) -> Data:
        """Validate codes and return coverage status."""
        lookup_result = await self.lookup_codes()
        data = lookup_result.data

        results = data.get("results", [])

        # Validation logic
        validation = {
            "all_valid": all(r["description"] != "Unknown code" for r in results),
            "has_common_conditions": any(r.get("common", False) for r in results),
            "categories": list(set(r.get("category", "Unknown") for r in results)),
            "requires_review": any(r.get("category") in ["Mental health", "Cosmetic"] for r in results),
            "code_details": results,
        }

        return Data(data=validation)
