"""Validate diagnosis tool for ICD-10 code validation.

This module provides a tool for validating ICD-10 diagnosis codes,
checking coverage status and retrieving code descriptions.
"""

from typing import Any, Dict, List, Optional

from tools.base import BaseTool


# Mock ICD-10 data for common diagnoses
ICD10_DATABASE = {
    "A00": {"description": "Cholera", "category": "Infectious diseases", "covered": True},
    "A01": {"description": "Typhoid and paratyphoid fevers", "category": "Infectious diseases", "covered": True},
    "B01": {"description": "Varicella [chickenpox]", "category": "Infectious diseases", "covered": True},
    "C78": {"description": "Secondary malignant neoplasm of respiratory and digestive organs", "category": "Neoplasms", "covered": True},
    "E10": {"description": "Type 1 diabetes mellitus", "category": "Endocrine/metabolic", "covered": True},
    "E11": {"description": "Type 2 diabetes mellitus", "category": "Endocrine/metabolic", "covered": True},
    "E66": {"description": "Obesity", "category": "Endocrine/metabolic", "covered": True},
    "F32": {"description": "Depressive episode", "category": "Mental disorders", "covered": True},
    "G40": {"description": "Epilepsy", "category": "Nervous system", "covered": True},
    "I10": {"description": "Essential (primary) hypertension", "category": "Circulatory system", "covered": True},
    "I21": {"description": "Acute myocardial infarction", "category": "Circulatory system", "covered": True},
    "I50": {"description": "Heart failure", "category": "Circulatory system", "covered": True},
    "J06": {"description": "Acute upper respiratory infections", "category": "Respiratory system", "covered": True},
    "J18": {"description": "Pneumonia, unspecified organism", "category": "Respiratory system", "covered": True},
    "J44": {"description": "Chronic obstructive pulmonary disease", "category": "Respiratory system", "covered": True},
    "J45": {"description": "Asthma", "category": "Respiratory system", "covered": True},
    "K29": {"description": "Gastritis and duodenitis", "category": "Digestive system", "covered": True},
    "K35": {"description": "Acute appendicitis", "category": "Digestive system", "covered": True},
    "K70": {"description": "Alcoholic liver disease", "category": "Digestive system", "covered": True},
    "M16": {"description": "Osteoarthritis of hip", "category": "Musculoskeletal", "covered": True},
    "M17": {"description": "Osteoarthritis of knee", "category": "Musculoskeletal", "covered": True},
    "N18": {"description": "Chronic kidney disease", "category": "Genitourinary", "covered": True},
    "O80": {"description": "Encounter for full-term uncomplicated delivery", "category": "Pregnancy/childbirth", "covered": True},
    "S72": {"description": "Fracture of femur", "category": "Injuries", "covered": True},
    "Z51": {"description": "Encounter for other aftercare", "category": "Factors influencing health", "covered": True},
}

# Category mappings for broader code lookups
ICD_CATEGORIES = {
    "A": "Infectious and parasitic diseases",
    "B": "Infectious and parasitic diseases",
    "C": "Neoplasms",
    "D": "Blood and immune disorders",
    "E": "Endocrine, nutritional and metabolic diseases",
    "F": "Mental and behavioral disorders",
    "G": "Diseases of the nervous system",
    "H": "Diseases of the eye and adnexa / ear and mastoid process",
    "I": "Diseases of the circulatory system",
    "J": "Diseases of the respiratory system",
    "K": "Diseases of the digestive system",
    "L": "Diseases of the skin and subcutaneous tissue",
    "M": "Diseases of the musculoskeletal system",
    "N": "Diseases of the genitourinary system",
    "O": "Pregnancy, childbirth and the puerperium",
    "P": "Certain conditions originating in the perinatal period",
    "Q": "Congenital malformations",
    "R": "Symptoms, signs and abnormal findings",
    "S": "Injury, poisoning and certain other consequences",
    "T": "Injury, poisoning and certain other consequences",
    "U": "Special purposes",
    "V": "External causes of morbidity",
    "W": "External causes of morbidity",
    "X": "External causes of morbidity",
    "Y": "External causes of morbidity",
    "Z": "Factors influencing health status",
}

# Excluded conditions (not covered by standard insurance)
EXCLUDED_CONDITIONS = [
    "cosmetic", "elective", "experimental", "alternative_medicine",
    "self_inflicted", "substance_abuse_elective"
]


class ValidateDiagnosisTool(BaseTool):
    """Tool for validating ICD-10 diagnosis codes.

    Validates ICD-10 codes for format correctness, retrieves descriptions,
    and checks coverage status under insurance policies.
    """

    name = "validate_diagnosis"
    description = (
        "Validate ICD-10 diagnosis codes for format correctness, "
        "retrieve code descriptions, and check insurance coverage status. "
        "Supports both specific codes and code ranges."
    )
    parameters: Dict[str, Any] = {
        "type": "object",
        "properties": {
            "diagnosis_codes": {
                "type": "array",
                "description": "List of ICD-10 diagnosis codes to validate",
                "items": {
                    "type": "string",
                    "description": "ICD-10 code (e.g., 'J18.9', 'E11', 'I10')"
                }
            },
            "policy_number": {
                "type": "string",
                "description": "Insurance policy number for coverage checking"
            }
        },
        "required": ["diagnosis_codes"]
    }

    async def execute(
        self,
        diagnosis_codes: List[str],
        policy_number: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Execute diagnosis validation.

        Args:
            diagnosis_codes: List of ICD-10 codes to validate
            policy_number: Optional policy number for coverage checking

        Returns:
            Dictionary with validation results including issues list with severity levels
        """
        if not diagnosis_codes:
            return {
                "success": False,
                "valid": False,
                "severity_score": 1.0,
                "issues": [{
                    "field": "diagnosis_codes",
                    "severity": "high",
                    "message": "No diagnosis codes provided",
                    "details": {}
                }],
                "codes": [],
                "summary": "Validation failed: No diagnosis codes provided"
            }

        results = []
        issues = []
        warnings = []

        for code in diagnosis_codes:
            code_result = self._validate_code(code, policy_number)
            results.append(code_result)

            if not code_result["valid_format"]:
                issues.append({
                    "field": f"code_{code}",
                    "severity": "high",
                    "message": f"Invalid ICD-10 code format: {code}",
                    "details": {
                        "code": code,
                        "error": code_result.get("format_error", "Unknown format error")
                    }
                })
            elif not code_result["found"]:
                warnings.append({
                    "field": f"code_{code}",
                    "severity": "low",
                    "message": f"Code not found in database: {code}. May require manual review.",
                    "details": {"code": code}
                })
            elif not code_result["covered"]:
                issues.append({
                    "field": f"code_{code}",
                    "severity": "high",
                    "message": f"Diagnosis not covered by policy: {code}",
                    "details": {
                        "code": code,
                        "description": code_result.get("description", ""),
                        "reason": code_result.get("exclusion_reason", "Policy exclusion")
                    }
                })

        # Check for duplicate codes
        code_counts = {}
        for code in diagnosis_codes:
            normalized = code.upper().replace(".", "")
            code_counts[normalized] = code_counts.get(normalized, 0) + 1

        for code, count in code_counts.items():
            if count > 1:
                warnings.append({
                    "field": "diagnosis_codes",
                    "severity": "low",
                    "message": f"Duplicate diagnosis code detected: {code}",
                    "details": {"code": code, "occurrences": count}
                })

        all_issues = issues + warnings
        severity_score = self._calculate_severity_score(all_issues)
        valid_codes = sum(1 for r in results if r["valid_format"] and r["covered"])

        return {
            "success": True,
            "valid": len(issues) == 0,
            "severity_score": severity_score,
            "issues": all_issues,
            "codes": results,
            "total_codes": len(diagnosis_codes),
            "valid_codes": valid_codes,
            "invalid_codes": len([r for r in results if not r["valid_format"]]),
            "excluded_codes": len([r for r in results if r["valid_format"] and not r["covered"]]),
            "summary": self._generate_summary(results, diagnosis_codes, len(issues) == 0)
        }

    def _validate_code(self, code: str, policy_number: Optional[str] = None) -> Dict[str, Any]:
        """Validate a single ICD-10 code."""
        result = {
            "code": code,
            "valid_format": False,
            "found": False,
            "covered": False,
            "description": None,
            "category": None,
            "format_error": None,
            "exclusion_reason": None
        }

        # Normalize code
        normalized = code.upper().replace(".", "").strip()

        # Validate format: starts with letter, followed by 2+ digits
        if not normalized:
            result["format_error"] = "Empty code"
            return result

        if not normalized[0].isalpha():
            result["format_error"] = "Code must start with a letter"
            return result

        if len(normalized) < 3:
            result["format_error"] = "Code must be at least 3 characters"
            return result

        if not normalized[1:3].isdigit():
            result["format_error"] = "Second and third characters must be digits"
            return result

        result["valid_format"] = True

        # Look up in database
        # Try exact match first
        prefix = normalized[:3]
        if prefix in ICD10_DATABASE:
            result["found"] = True
            result["description"] = ICD10_DATABASE[prefix]["description"]
            result["category"] = ICD10_DATABASE[prefix]["category"]
            result["covered"] = ICD10_DATABASE[prefix]["covered"]
        else:
            # Try category lookup
            category = ICD_CATEGORIES.get(normalized[0])
            if category:
                result["found"] = True
                result["description"] = f"{category} (code {code})"
                result["category"] = category
                result["covered"] = True  # Assume covered if valid category

        # Check exclusions
        if result["found"] and result["description"]:
            desc_lower = result["description"].lower()
            for exclusion in EXCLUDED_CONDITIONS:
                if exclusion.replace("_", " ") in desc_lower:
                    result["covered"] = False
                    result["exclusion_reason"] = f"Excluded condition: {exclusion}"
                    break

        return result

    def _calculate_severity_score(self, issues: List[Dict[str, Any]]) -> float:
        """Calculate overall severity score from 0.0 (clean) to 1.0 (critical)."""
        if not issues:
            return 0.0

        weights = {"high": 1.0, "medium": 0.5, "low": 0.2}
        total_weight = sum(weights.get(issue["severity"], 0.5) for issue in issues)
        return min(1.0, total_weight / 5.0)

    def _generate_summary(
        self,
        results: List[Dict[str, Any]],
        codes: List[str],
        is_valid: bool
    ) -> str:
        """Generate human-readable summary of validation results."""
        valid_count = sum(1 for r in results if r["valid_format"] and r["covered"])
        invalid_count = sum(1 for r in results if not r["valid_format"])
        excluded_count = sum(1 for r in results if r["valid_format"] and not r["covered"])

        if len(codes) == 0:
            return "No diagnosis codes to validate"

        status = "passed" if is_valid else "failed"
        parts = [f"{valid_count}/{len(codes)} codes valid and covered"]

        if invalid_count > 0:
            parts.append(f"{invalid_count} invalid")
        if excluded_count > 0:
            parts.append(f"{excluded_count} excluded")

        return f"Validation {status}: {', '.join(parts)}"
