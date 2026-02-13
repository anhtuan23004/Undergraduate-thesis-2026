"""ICD-10 lookup tool."""
from typing import Any, Dict, List

from tools.base import BaseTool


# Mock ICD-10 data for demo
ICD_DESCRIPTIONS = {
    "A00": "Cholera",
    "B01": "Varicella [chickenpox]",
    "C78": "Secondary malignant neoplasm of respiratory and digestive organs",
    "E11": "Type 2 diabetes mellitus",
    "I10": "Essential (primary) hypertension",
    "J06": "Acute upper respiratory infections",
    "J18": "Pneumonia, unspecified",
    "K29": "Gastritis and duodenitis",
    "M16": "Osteoarthritis of hip",
    "S72": "Fracture of femur"
}

ICD_CATEGORIES = {
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

        results = [self._lookup_code(code) for code in codes]
        all_valid = all(r["valid"] for r in results)
        covered_count = sum(1 for r in results if r["covered"])

        return {
            "status": "success" if all_valid else "partial",
            "codes": results,
            "total_codes": len(codes),
            "valid_codes": sum(1 for r in results if r["valid"]),
            "covered_codes": covered_count,
            "summary": f"{len(results)} codes checked, {covered_count} covered"
        }

    def _lookup_code(self, code: str) -> Dict[str, Any]:
        """Lookup a single ICD-10 code."""
        is_valid = len(code) >= 3 and code[0].isalpha()
        prefix = code[:3].upper()

        return {
            "code": code,
            "valid": is_valid,
            "description": ICD_DESCRIPTIONS.get(prefix, f"Diagnosis code {code}"),
            "covered": is_valid,
            "category": ICD_CATEGORIES.get(code[0].upper(), "Other") if code else "Unknown"
        }
