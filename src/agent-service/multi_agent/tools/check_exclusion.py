"""Check exclusion tool for policy exclusion validation.

This module provides a tool for checking if a claim or diagnosis
is excluded from coverage based on policy terms and conditions.
"""

from typing import Any, Dict, List, Optional

from multi_agent.tools.base import BaseTool


# Mock policy exclusions database
POLICY_EXCLUSIONS = {
    "POL-001": {
        "exclusions": [
            {"type": "condition", "value": "cosmetic surgery", "severity": "permanent"},
            {"type": "condition", "value": "pre-existing conditions", "severity": "waiting_period", "period_days": 365},
            {"type": "procedure", "value": "elective abortion", "severity": "permanent"},
            {"type": "treatment", "value": "experimental treatments", "severity": "permanent"},
            {"type": "condition", "value": "self-inflicted injuries", "severity": "permanent"},
        ],
        "waiting_periods": {
            "general": 30,
            "maternity": 270,
            "pre_existing": 365
        }
    },
    "POL-002": {
        "exclusions": [
            {"type": "condition", "value": "cosmetic surgery", "severity": "permanent"},
            {"type": "service", "value": "dental", "severity": "permanent"},
            {"type": "service", "value": "vision", "severity": "permanent"},
            {"type": "treatment", "value": "alternative medicine", "severity": "permanent"},
            {"type": "condition", "value": "substance abuse", "severity": "conditional"},
        ],
        "waiting_periods": {
            "general": 60,
            "maternity": 365,
            "pre_existing": 730
        }
    },
    "DEFAULT": {
        "exclusions": [
            {"type": "condition", "value": "cosmetic surgery", "severity": "permanent"},
            {"type": "treatment", "value": "experimental treatments", "severity": "permanent"},
        ],
        "waiting_periods": {
            "general": 30,
            "maternity": 270,
            "pre_existing": 365
        }
    }
}

# Common exclusion keywords by category
EXCLUSION_KEYWORDS = {
    "cosmetic": ["cosmetic", "aesthetic", "plastic surgery", "beauty"],
    "dental": ["dental", "tooth", "teeth", "orthodontic", "periodontal"],
    "vision": ["vision", "eye exam", "glasses", "contact lens", "refractive"],
    "maternity": ["pregnancy", "childbirth", "delivery", "maternity", "prenatal"],
    "pre_existing": ["pre-existing", "preexisting", "prior condition", "chronic"],
    "experimental": ["experimental", "investigational", "clinical trial"],
    "alternative": ["alternative medicine", "homeopathic", "acupuncture", "herbal"],
    "self_inflicted": ["self-inflicted", "self inflicted", "suicide attempt"],
    "substance_abuse": ["substance abuse", "drug addiction", "alcoholism"],
    "elective_abortion": ["elective abortion", "termination of pregnancy"],
}


class CheckExclusionTool(BaseTool):
    """Tool for checking policy exclusions.

    Checks if a diagnosis, procedure, or treatment is excluded from coverage
    based on the insurance policy terms and conditions.
    """

    name = "check_exclusion"
    description = (
        "Check if a diagnosis, procedure, or treatment is excluded from "
        "coverage based on policy terms. Validates against policy-specific "
        "exclusions and waiting periods."
    )
    parameters: Dict[str, Any] = {
        "type": "object",
        "properties": {
            "policy_number": {
                "type": "string",
                "description": "Insurance policy number"
            },
            "diagnosis_codes": {
                "type": "array",
                "description": "List of ICD-10 diagnosis codes",
                "items": {"type": "string"}
            },
            "procedures": {
                "type": "array",
                "description": "List of procedure names or CPT codes",
                "items": {"type": "string"}
            },
            "treatments": {
                "type": "array",
                "description": "List of treatment descriptions",
                "items": {"type": "string"}
            },
            "policy_start_date": {
                "type": "string",
                "description": "Policy start date (ISO format: YYYY-MM-DD)"
            },
            "service_date": {
                "type": "string",
                "description": "Date of service (ISO format: YYYY-MM-DD)"
            }
        },
        "required": ["policy_number"]
    }

    async def execute(
        self,
        policy_number: str,
        diagnosis_codes: Optional[List[str]] = None,
        procedures: Optional[List[str]] = None,
        treatments: Optional[List[str]] = None,
        policy_start_date: Optional[str] = None,
        service_date: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Execute exclusion check.

        Args:
            policy_number: Insurance policy number
            diagnosis_codes: List of ICD-10 diagnosis codes
            procedures: List of procedure names or CPT codes
            treatments: List of treatment descriptions
            policy_start_date: Policy start date (ISO format)
            service_date: Date of service (ISO format)

        Returns:
            Dictionary with exclusion check results including issues list
        """
        issues = []
        warnings = []

        # Get policy exclusions
        policy_data = POLICY_EXCLUSIONS.get(policy_number, POLICY_EXCLUSIONS["DEFAULT"])
        exclusions = policy_data.get("exclusions", [])
        waiting_periods = policy_data.get("waiting_periods", {})

        # Check waiting period
        if policy_start_date and service_date:
            waiting_issue = self._check_waiting_period(
                policy_start_date, service_date, waiting_periods
            )
            if waiting_issue:
                issues.append(waiting_issue)

        # Check diagnosis codes against exclusions
        if diagnosis_codes:
            for code in diagnosis_codes:
                exclusion_result = self._check_code_exclusion(code, exclusions)
                if exclusion_result["is_excluded"]:
                    issues.append({
                        "field": f"diagnosis_{code}",
                        "severity": "high",
                        "message": f"Diagnosis {code} is excluded from coverage",
                        "details": exclusion_result
                    })

        # Check procedures against exclusions
        if procedures:
            for procedure in procedures:
                exclusion_result = self._check_text_exclusion(procedure, exclusions)
                if exclusion_result["is_excluded"]:
                    issues.append({
                        "field": f"procedure_{procedure}",
                        "severity": "high",
                        "message": f"Procedure '{procedure}' is excluded from coverage",
                        "details": exclusion_result
                    })

        # Check treatments against exclusions
        if treatments:
            for treatment in treatments:
                exclusion_result = self._check_text_exclusion(treatment, exclusions)
                if exclusion_result["is_excluded"]:
                    issues.append({
                        "field": f"treatment_{treatment}",
                        "severity": "high",
                        "message": f"Treatment '{treatment}' is excluded from coverage",
                        "details": exclusion_result
                    })

        # Check for potential exclusions (warnings)
        all_items = (diagnosis_codes or []) + (procedures or []) + (treatments or [])
        for item in all_items:
            potential = self._check_potential_exclusion(item, exclusions)
            if potential["is_potential"]:
                warnings.append({
                    "field": "general",
                    "severity": "low",
                    "message": potential["message"],
                    "details": {"item": item, "category": potential["category"]}
                })

        all_issues = issues + warnings
        severity_score = self._calculate_severity_score(all_issues)
        is_excluded = len(issues) > 0

        return {
            "success": True,
            "excluded": is_excluded,
            "severity_score": severity_score,
            "issues": all_issues,
            "error_count": len(issues),
            "warning_count": len(warnings),
            "policy_number": policy_number,
            "exclusions_checked": len(exclusions),
            "summary": self._generate_summary(all_issues, is_excluded, policy_number)
        }

    def _check_waiting_period(
        self,
        policy_start_date: str,
        service_date: str,
        waiting_periods: Dict[str, int]
    ) -> Optional[Dict[str, Any]]:
        """Check if service falls within waiting period."""
        from datetime import datetime

        try:
            start = datetime.strptime(policy_start_date, "%Y-%m-%d")
            service = datetime.strptime(service_date, "%Y-%m-%d")
            days_elapsed = (service - start).days

            general_waiting = waiting_periods.get("general", 30)
            if days_elapsed < general_waiting:
                return {
                    "field": "waiting_period",
                    "severity": "high",
                    "message": f"Service within waiting period ({days_elapsed}/{general_waiting} days)",
                    "details": {
                        "days_elapsed": days_elapsed,
                        "waiting_period_days": general_waiting,
                        "policy_start": policy_start_date,
                        "service_date": service_date
                    }
                }
        except ValueError:
            return {
                "field": "dates",
                "severity": "medium",
                "message": "Invalid date format for waiting period check",
                "details": {
                    "policy_start": policy_start_date,
                    "service_date": service_date
                }
            }
        return None

    def _check_code_exclusion(self, code: str, exclusions: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Check if an ICD-10 code matches any exclusion."""
        result = {"is_excluded": False, "matched_exclusion": None, "reason": None}

        # Check for maternity-related codes (O codes)
        if code.upper().startswith("O"):
            for exclusion in exclusions:
                if "maternity" in exclusion["value"].lower():
                    result["is_excluded"] = True
                    result["matched_exclusion"] = exclusion
                    result["reason"] = "Maternity services may be subject to waiting period"
                    return result

        # Check for mental health codes (F codes) - substance abuse
        if code.upper().startswith("F"):
            for exclusion in exclusions:
                if "substance" in exclusion["value"].lower():
                    result["is_excluded"] = True
                    result["matched_exclusion"] = exclusion
                    result["reason"] = "Substance abuse-related conditions may be excluded"
                    return result

        return result

    def _check_text_exclusion(self, text: str, exclusions: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Check if text matches any exclusion."""
        result = {"is_excluded": False, "matched_exclusion": None, "reason": None}
        text_lower = text.lower()

        for exclusion in exclusions:
            exclusion_value = exclusion["value"].lower()
            if exclusion_value in text_lower:
                result["is_excluded"] = True
                result["matched_exclusion"] = exclusion
                result["reason"] = f"Matches exclusion: {exclusion['value']}"
                return result

        return result

    def _check_potential_exclusion(self, item: str, exclusions: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Check for potential exclusions based on keywords."""
        result = {"is_potential": False, "category": None, "message": None}
        item_lower = item.lower()

        for category, keywords in EXCLUSION_KEYWORDS.items():
            for keyword in keywords:
                if keyword in item_lower:
                    # Check if this category is excluded
                    for exclusion in exclusions:
                        if category.replace("_", " ") in exclusion["value"].lower():
                            result["is_potential"] = True
                            result["category"] = category
                            result["message"] = f"Item may fall under excluded category: {category}"
                            return result

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
        issues: List[Dict[str, Any]],
        is_excluded: bool,
        policy_number: str
    ) -> str:
        """Generate human-readable summary of exclusion check."""
        if not issues:
            return f"No exclusions found for policy {policy_number}"

        high_count = sum(1 for i in issues if i["severity"] == "high")
        medium_count = sum(1 for i in issues if i["severity"] == "medium")
        low_count = sum(1 for i in issues if i["severity"] == "low")

        if is_excluded:
            return f"Claim EXCLUDED under policy {policy_number}: {high_count} exclusion(s) found"

        parts = []
        if medium_count > 0:
            parts.append(f"{medium_count} warning(s)")
        if low_count > 0:
            parts.append(f"{low_count} note(s)")

        return f"No exclusions, but {', '.join(parts)} for policy {policy_number}"
