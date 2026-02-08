"""ICD-10 lookup tool."""
from typing import Any, Dict, List

from tools.base import BaseTool


class ICDLookupTool(BaseTool):
    """Tool for looking up ICD-10 diagnosis codes."""

    name = "icd_lookup"
    description = "Validate ICD-10 diagnosis codes and check if they are covered by insurance"

    async def arun(self, codes: List[str], **kwargs) -> Dict[str, Any]:
        """Lookup ICD-10 codes.

        Args:
            codes: List of ICD-10 codes

        Returns:
            Validation results with coverage info
        """
        if not codes:
            return {
                "status": "error",
                "message": "No ICD codes provided",
                "summary": "Missing diagnosis codes"
            }

        # TODO: Connect to actual ICD database
        # For now, return mock data
        results = []
        for code in codes:
            # Simple validation - real implementation would query database
            is_valid = len(code) >= 3 and code[0].isalpha()

            results.append({
                "code": code,
                "valid": is_valid,
                "description": self._get_mock_description(code),
                "covered": is_valid,  # Assume valid codes are covered
                "category": self._get_category(code)
            })

        all_valid = all(r["valid"] for r in results)
        all_covered = all(r["covered"] for r in results)

        return {
            "status": "success" if all_valid else "partial",
            "codes": results,
            "total_codes": len(codes),
            "valid_codes": sum(1 for r in results if r["valid"]),
            "covered_codes": sum(1 for r in results if r["covered"]),
            "summary": f"{len(results)} codes checked, {sum(1 for r in results if r['covered'])} covered"
        }

    def _get_mock_description(self, code: str) -> str:
        """Get mock description for demo."""
        descriptions = {
            "A00": "Cholera",
            "B01": "Varicella [chickenpox]",
            "C78": "Secondary malignant neoplasm of respiratory and digestive organs",
            "E11": "Type 2 diabetes mellitus",
            "I10": "Essential (primary) hypertension",
            "J06": "Acute upper respiratory infections",
            "K29": "Gastritis and duodenitis",
            "M16": "Osteoarthritis of hip",
            "S72": "Fracture of femur"
        }

        # Match first 3 characters
        prefix = code[:3].upper()
        return descriptions.get(prefix, f"Diagnosis code {code}")

    def _get_category(self, code: str) -> str:
        """Get category from first character."""
        categories = {
            "A": "Infectious diseases",
            "B": "Infectious diseases",
            "C": "Neoplasms",
            "D": "Blood and immune disorders",
            "E": "Endocrine/metabolic",
            "F": "Mental disorders",
            "G": "Nervous system",
            "H": "Eye/ear disorders",
            "I": "Circulatory system",
            "J": "Respiratory system",
            "K": "Digestive system",
            "M": "Musculoskeletal",
            "S": "Injuries"
        }

        first_char = code[0].upper() if code else ""
        return categories.get(first_char, "Other")
