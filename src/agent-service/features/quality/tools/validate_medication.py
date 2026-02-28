"""Validate medication tool for medication-diagnosis validation.

This module provides a tool for validating medications against diagnoses,
checking for drug interactions, contraindications, and coverage status.
"""

from typing import Any, Dict, List, Optional

from config import settings
from core.base.tool import BaseTool


# Mock medication database with indications and contraindications
MEDICATION_DATABASE = {
    "paracetamol": {
        "generic_name": "Acetaminophen",
        "indications": ["pain", "fever", "J06", "J18", "headache"],
        "contraindications": ["severe_liver_disease"],
        "category": "analgesic/antipyretic",
        "covered": True
    },
    "ibuprofen": {
        "generic_name": "Ibuprofen",
        "indications": ["pain", "inflammation", "fever", "M16", "M17", "headache"],
        "contraindications": ["peptic_ulcer", "bleeding_disorders", "K29"],
        "category": "NSAID",
        "covered": True
    },
    "amoxicillin": {
        "generic_name": "Amoxicillin",
        "indications": ["bacterial_infection", "J06", "J18", "H66", "K35"],
        "contraindications": ["penicillin_allergy"],
        "category": "antibiotic",
        "covered": True
    },
    "metformin": {
        "generic_name": "Metformin",
        "indications": ["E10", "E11", "diabetes"],
        "contraindications": ["severe_kidney_disease", "ketoacidosis", "N18"],
        "category": "antidiabetic",
        "covered": True
    },
    "insulin": {
        "generic_name": "Insulin",
        "indications": ["E10", "E11", "diabetes", "ketoacidosis"],
        "contraindications": ["hypoglycemia"],
        "category": "antidiabetic",
        "covered": True
    },
    "atorvastatin": {
        "generic_name": "Atorvastatin",
        "indications": ["hyperlipidemia", "I21", "I10", "cardiovascular_prevention"],
        "contraindications": ["liver_disease", "pregnancy", "K70"],
        "category": "statin",
        "covered": True
    },
    "amlodipine": {
        "generic_name": "Amlodipine",
        "indications": ["I10", "hypertension", "angina", "I20"],
        "contraindications": ["severe_aortic_stenosis", "cardiogenic_shock"],
        "category": "calcium_channel_blocker",
        "covered": True
    },
    "salbutamol": {
        "generic_name": "Albuterol",
        "indications": ["J45", "asthma", "COPD", "J44", "bronchospasm"],
        "contraindications": ["hypersensitivity"],
        "category": "bronchodilator",
        "covered": True
    },
    "omeprazole": {
        "generic_name": "Omeprazole",
        "indications": ["K29", "GERD", "peptic_ulcer", "dyspepsia"],
        "contraindications": ["hypersensitivity"],
        "category": "PPI",
        "covered": True
    },
    "morphine": {
        "generic_name": "Morphine",
        "indications": ["severe_pain", "S72", "post_surgical", "cancer_pain"],
        "contraindications": ["respiratory_depression", "increased_ICP"],
        "category": "opioid",
        "covered": True
    },
    "warfarin": {
        "generic_name": "Warfarin",
        "indications": ["atrial_fibrillation", "DVT", "PE", "stroke_prevention"],
        "contraindications": ["bleeding", "pregnancy", "hemorrhagic_stroke"],
        "category": "anticoagulant",
        "covered": True
    },
    "aspirin": {
        "generic_name": "Aspirin",
        "indications": ["pain", "fever", "I21", "stroke_prevention", "I10"],
        "contraindications": ["bleeding_disorders", "peptic_ulcer", "K29", "children_viral"],
        "category": "NSAID/antiplatelet",
        "covered": True
    }
}

# Drug interaction database
DRUG_INTERACTIONS = {
    ("warfarin", "aspirin"): {
        "severity": "high",
        "mechanism": "Increased bleeding risk",
        "recommendation": "Monitor INR closely or consider alternative"
    },
    ("metformin", "contrast_dye"): {
        "severity": "high",
        "mechanism": "Risk of lactic acidosis",
        "recommendation": "Hold metformin 48 hours before/after contrast"
    },
    ("ibuprofen", "aspirin"): {
        "severity": "medium",
        "mechanism": "Reduced antiplatelet effect of aspirin",
        "recommendation": "Separate dosing by 8 hours or use alternative"
    },
    ("amoxicillin", "warfarin"): {
        "severity": "medium",
        "mechanism": "May affect INR",
        "recommendation": "Monitor INR"
    },
    ("omeprazole", "clopidogrel"): {
        "severity": "medium",
        "mechanism": "Reduced clopidogrel effectiveness",
        "recommendation": "Consider pantoprazole instead"
    }
}

# Medications requiring special authorization
# Prior authorization medications loaded from settings
PRIOR_AUTH_MEDICATIONS = settings.prior_auth_medications_list


class ValidateMedicationTool(BaseTool):
    """Tool for validating medications against diagnoses.

    Validates that prescribed medications are appropriate for the diagnosed
    conditions, checks for drug interactions, contraindications, and coverage.
    """

    name = "validate_medication"
    description = (
        "Validate medications against diagnosis codes. Checks for appropriate "
        "indications, drug interactions, contraindications, and insurance coverage. "
        "Identifies medications that may require prior authorization."
    )
    parameters: Dict[str, Any] = {
        "type": "object",
        "properties": {
            "medications": {
                "type": "array",
                "description": "List of medication names (generic or brand)",
                "items": {"type": "string"}
            },
            "diagnosis_codes": {
                "type": "array",
                "description": "List of ICD-10 diagnosis codes",
                "items": {"type": "string"}
            },
            "patient_age": {
                "type": "integer",
                "description": "Patient age in years"
            },
            "patient_conditions": {
                "type": "array",
                "description": "Additional patient conditions (e.g., 'pregnancy', 'liver_disease')",
                "items": {"type": "string"}
            }
        },
        "required": ["medications", "diagnosis_codes"]
    }

    async def execute(
        self,
        medications: List[str],
        diagnosis_codes: List[str],
        patient_age: Optional[int] = None,
        patient_conditions: Optional[List[str]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Execute medication validation.

        Args:
            medications: List of medication names
            diagnosis_codes: List of ICD-10 diagnosis codes
            patient_age: Patient age in years
            patient_conditions: Additional patient conditions

        Returns:
            Dictionary with validation results including issues list
        """
        issues = []
        warnings = []
        medication_results = []

        patient_conditions = patient_conditions or []

        # Validate each medication
        for med in medications:
            med_result = self._validate_medication(
                med, diagnosis_codes, patient_age, patient_conditions
            )
            medication_results.append(med_result)

            if not med_result["found"]:
                warnings.append({
                    "field": f"medication_{med}",
                    "severity": "low",
                    "message": f"Medication '{med}' not found in database. Manual review recommended.",
                    "details": {"medication": med}
                })
            else:
                # Check indication match
                if not med_result["indication_match"]:
                    issues.append({
                        "field": f"medication_{med}",
                        "severity": "high",
                        "message": f"Medication '{med}' may not be indicated for the diagnosed conditions",
                        "details": {
                            "medication": med,
                            "diagnoses": diagnosis_codes,
                            "indications": med_result.get("known_indications", [])
                        }
                    })

                # Check contraindications
                if med_result["contraindicated"]:
                    issues.append({
                        "field": f"medication_{med}",
                        "severity": "high",
                        "message": f"Medication '{med}' is contraindicated for this patient",
                        "details": {
                            "medication": med,
                            "contraindications": med_result.get("matched_contraindications", [])
                        }
                    })

                # Check prior authorization
                if med_result["requires_prior_auth"]:
                    warnings.append({
                        "field": f"medication_{med}",
                        "severity": "medium",
                        "message": f"Medication '{med}' may require prior authorization",
                        "details": {"medication": med}
                    })

        # Check drug interactions
        interactions = self._check_interactions(medications)
        for interaction in interactions:
            if interaction["severity"] == "high":
                issues.append({
                    "field": "drug_interaction",
                    "severity": "high",
                    "message": f"Drug interaction: {interaction['drug1']} + {interaction['drug2']}",
                    "details": interaction
                })
            else:
                warnings.append({
                    "field": "drug_interaction",
                    "severity": "medium",
                    "message": f"Potential interaction: {interaction['drug1']} + {interaction['drug2']}",
                    "details": interaction
                })

        # Check for duplicate medications (same class)
        duplicates = self._check_duplicate_therapy(medications)
        for dup in duplicates:
            warnings.append({
                "field": "duplicate_therapy",
                "severity": "low",
                "message": f"Duplicate therapy detected: {dup['medications']} are in the same class ({dup['class']})",
                "details": dup
            })

        all_issues = issues + warnings
        severity_score = self._calculate_severity_score(all_issues)

        return {
            "success": True,
            "valid": len(issues) == 0,
            "severity_score": severity_score,
            "issues": all_issues,
            "error_count": len(issues),
            "warning_count": len(warnings),
            "medications": medication_results,
            "interactions": interactions,
            "summary": self._generate_summary(medications, all_issues, len(issues) == 0)
        }

    def _validate_medication(
        self,
        medication: str,
        diagnosis_codes: List[str],
        patient_age: Optional[int],
        patient_conditions: List[str]
    ) -> Dict[str, Any]:
        """Validate a single medication."""
        result = {
            "medication": medication,
            "found": False,
            "generic_name": None,
            "category": None,
            "indication_match": False,
            "contraindicated": False,
            "requires_prior_auth": False,
            "covered": False,
            "known_indications": [],
            "matched_contraindications": []
        }

        # Look up medication (case-insensitive)
        med_key = self._normalize_string(medication).strip()
        med_data = None

        # Direct match
        if med_key in MEDICATION_DATABASE:
            med_data = MEDICATION_DATABASE[med_key]
        else:
            # Try to find by generic name
            for key, data in MEDICATION_DATABASE.items():
                if data["generic_name"].lower() == med_key:
                    med_data = data
                    break

        if not med_data:
            return result

        result["found"] = True
        result["generic_name"] = med_data["generic_name"]
        result["category"] = med_data["category"]
        result["known_indications"] = med_data["indications"]
        result["covered"] = med_data["covered"]

        # Check indication match
        indications = med_data["indications"]
        for code in diagnosis_codes:
            code_upper = code.upper()
            # Direct code match
            if code_upper in indications:
                result["indication_match"] = True
                break
            # Category prefix match
            for ind in indications:
                if len(ind) == 3 and code_upper.startswith(ind):
                    result["indication_match"] = True
                    break

        # Check contraindications
        contraindications = med_data["contraindications"]
        for condition in patient_conditions:
            condition_lower = self._normalize_string(condition)
            for contraindication in contraindications:
                if contraindication.lower() in condition_lower:
                    result["contraindicated"] = True
                    result["matched_contraindications"].append(contraindication)

        # Check diagnosis-based contraindications
        for code in diagnosis_codes:
            code_upper = code.upper().replace(".", "")
            if code_upper in contraindications:
                result["contraindicated"] = True
                result["matched_contraindications"].append(code_upper)

        # Check prior authorization
        if med_key in PRIOR_AUTH_MEDICATIONS:
            result["requires_prior_auth"] = True

        # Age-based checks
        if patient_age is not None:
            if patient_age < 18 and med_key in ["aspirin", "warfarin"]:
                result["contraindicated"] = True
                result["matched_contraindications"].append("age_restriction")

        return result

    def _check_interactions(self, medications: List[str]) -> List[Dict[str, Any]]:
        """Check for drug-drug interactions."""
        interactions = []
        med_lower = [m.lower().strip() for m in medications]

        for i, med1 in enumerate(med_lower):
            for med2 in med_lower[i + 1:]:
                # Check both orderings
                pair = (med1, med2)
                reverse_pair = (med2, med1)

                if pair in DRUG_INTERACTIONS:
                    interaction = DRUG_INTERACTIONS[pair].copy()
                    interaction["drug1"] = med1
                    interaction["drug2"] = med2
                    interactions.append(interaction)
                elif reverse_pair in DRUG_INTERACTIONS:
                    interaction = DRUG_INTERACTIONS[reverse_pair].copy()
                    interaction["drug1"] = med2
                    interaction["drug2"] = med1
                    interactions.append(interaction)

        return interactions

    def _check_duplicate_therapy(self, medications: List[str]) -> List[Dict[str, Any]]:
        """Check for duplicate therapy (same class)."""
        duplicates = []
        med_classes = {}

        for med in medications:
            med_key = med.lower().strip()
            med_data = MEDICATION_DATABASE.get(med_key)
            if med_data:
                category = med_data["category"]
                if category in med_classes:
                    med_classes[category].append(med)
                else:
                    med_classes[category] = [med]

        for category, meds in med_classes.items():
            if len(meds) > 1 and category in ["NSAID", "analgesic/antipyretic", "antibiotic"]:
                duplicates.append({
                    "class": category,
                    "medications": meds
                })

        return duplicates

    def _generate_summary(
        self,
        medications: List[str],
        issues: List[Dict[str, Any]],
        is_valid: bool
    ) -> str:
        """Generate human-readable summary of validation results."""
        high_count = sum(1 for i in issues if i["severity"] == "high")
        medium_count = sum(1 for i in issues if i["severity"] == "medium")
        low_count = sum(1 for i in issues if i["severity"] == "low")

        status = "passed" if is_valid else "failed"
        parts = [f"{len(medications)} medication(s) checked"]

        if high_count > 0:
            parts.append(f"{high_count} error(s)")
        if medium_count > 0:
            parts.append(f"{medium_count} warning(s)")
        if low_count > 0:
            parts.append(f"{low_count} note(s)")

        return f"Validation {status}: {', '.join(parts)}"
