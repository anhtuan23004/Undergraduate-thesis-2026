"""Benefit classification tool.

This module provides a tool for classifying medical benefits into
standard categories based on extracted document content.
"""

from typing import Any, Dict, List, Optional

from multi_agent.tools.base import BaseTool


# Standard benefit categories for health insurance
BENEFIT_CATEGORIES = {
    "inpatient": {
        "name": "Inpatient Treatment",
        "description": "Hospital admission and overnight stay",
        "keywords": ["hospitalization", "admission", "inpatient", "room charge", "bed fee"]
    },
    "outpatient": {
        "name": "Outpatient Treatment",
        "description": "Medical treatment without hospital admission",
        "keywords": ["outpatient", "clinic", "consultation", "examination", "check-up"]
    },
    "emergency": {
        "name": "Emergency Treatment",
        "description": "Urgent medical care in emergency department",
        "keywords": ["emergency", "urgent care", "ambulance", "ER", "casualty"]
    },
    "surgery": {
        "name": "Surgical Procedures",
        "description": "Operating room procedures and surgeries",
        "keywords": ["surgery", "operation", "surgical", "OR", "procedure"]
    },
    "medication": {
        "name": "Medication",
        "description": "Prescribed drugs and medicines",
        "keywords": ["medication", "drug", "medicine", "pharmacy", "prescription"]
    },
    "diagnostic": {
        "name": "Diagnostic Tests",
        "description": "Lab tests, imaging, and diagnostic procedures",
        "keywords": ["x-ray", "MRI", "CT scan", "ultrasound", "blood test", "lab", "diagnostic"]
    },
    "dental": {
        "name": "Dental Treatment",
        "description": "Dental procedures and oral care",
        "keywords": ["dental", "dentist", "tooth", "oral", "filling", "extraction"]
    },
    "maternity": {
        "name": "Maternity",
        "description": "Pregnancy and childbirth related",
        "keywords": ["maternity", "pregnancy", "childbirth", "delivery", "prenatal", "postnatal"]
    },
    "mental_health": {
        "name": "Mental Health",
        "description": "Psychiatric and psychological services",
        "keywords": ["psychiatric", "psychology", "mental health", "counseling", "therapy"]
    },
    "rehabilitation": {
        "name": "Rehabilitation",
        "description": "Physical therapy and rehabilitation services",
        "keywords": ["rehabilitation", "physiotherapy", "physical therapy", "rehab"]
    }
}


class ClassifyBenefitTool(BaseTool):
    """Tool for classifying medical benefits into standard categories.

    Analyzes extracted document content to determine the type of
    medical benefit being claimed.
    """

    name = "classify_benefit"
    description = (
        "Classify the medical benefit type based on diagnosis, procedures, "
        "and treatment details from claim documents. Returns standard "
        "benefit categories like inpatient, outpatient, surgery, etc."
    )
    parameters: Dict[str, Any] = {
        "type": "object",
        "properties": {
            "diagnosis": {
                "type": "string",
                "description": "Primary diagnosis or medical condition"
            },
            "diagnosis_codes": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of ICD-10 diagnosis codes"
            },
            "procedures": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of medical procedures performed"
            },
            "medications": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of medications prescribed or administered"
            },
            "hospital_stay_days": {
                "type": "number",
                "description": "Number of days patient stayed in hospital"
            },
            "treatment_location": {
                "type": "string",
                "description": "Where treatment was provided (hospital, clinic, etc.)"
            },
            "document_text": {
                "type": "string",
                "description": "Raw text from the document for keyword analysis"
            }
        },
        "required": []
    }

    async def execute(
        self,
        diagnosis: Optional[str] = None,
        diagnosis_codes: Optional[List[str]] = None,
        procedures: Optional[List[str]] = None,
        medications: Optional[List[str]] = None,
        hospital_stay_days: Optional[int] = None,
        treatment_location: Optional[str] = None,
        document_text: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Execute benefit classification.

        Args:
            diagnosis: Primary diagnosis description
            diagnosis_codes: ICD-10 codes
            procedures: Medical procedures performed
            medications: Medications prescribed
            hospital_stay_days: Length of hospital stay
            treatment_location: Where treatment occurred
            document_text: Raw document text for analysis

        Returns:
            Dictionary with classification results
        """
        scores = {category: 0.0 for category in BENEFIT_CATEGORIES}
        evidence = {category: [] for category in BENEFIT_CATEGORIES}

        # Combine all text for analysis
        text_to_analyze = ""
        if document_text:
            text_to_analyze += document_text.lower() + " "
        if diagnosis:
            text_to_analyze += diagnosis.lower() + " "
        if treatment_location:
            text_to_analyze += treatment_location.lower() + " "

        # Analyze procedures
        if procedures:
            for proc in procedures:
                text_to_analyze += proc.lower() + " "

        # Analyze medications
        if medications:
            for med in medications:
                text_to_analyze += med.lower() + " "

        # Score based on keyword matching
        for category, info in BENEFIT_CATEGORIES.items():
            for keyword in info["keywords"]:
                if keyword in text_to_analyze:
                    scores[category] += 1.0
                    evidence[category].append(f"Keyword match: '{keyword}'")

        # Boost scores based on structured data
        if hospital_stay_days and hospital_stay_days > 0:
            scores["inpatient"] += 3.0
            evidence["inpatient"].append(f"Hospital stay: {hospital_stay_days} days")

        if procedures:
            for proc in procedures:
                proc_lower = proc.lower()
                if any(surg in proc_lower for surg in ["surgery", "operation", "excision", "removal"]):
                    scores["surgery"] += 2.0
                    evidence["surgery"].append(f"Surgical procedure: {proc}")

        if medications:
            scores["medication"] += 1.0
            evidence["medication"].append(f"{len(medications)} medications prescribed")

        # ICD code analysis
        if diagnosis_codes:
            for code in diagnosis_codes:
                code_upper = code.upper()
                # Mental health codes (F00-F99)
                if code_upper.startswith("F"):
                    scores["mental_health"] += 2.0
                    evidence["mental_health"].append(f"Mental health ICD code: {code}")
                # Pregnancy codes (O00-O99)
                elif code_upper.startswith("O"):
                    scores["maternity"] += 2.0
                    evidence["maternity"].append(f"Maternity ICD code: {code}")
                # Injury/poisoning (S00-T98) - often emergency
                elif code_upper.startswith(("S", "T")):
                    scores["emergency"] += 1.0
                    evidence["emergency"].append(f"Injury ICD code: {code}")

        # Determine primary and secondary categories
        sorted_categories = sorted(
            scores.items(),
            key=lambda x: x[1],
            reverse=True
        )

        primary_category = None
        primary_score = 0.0
        secondary_categories = []

        for category, score in sorted_categories:
            if score > 0:
                if primary_category is None:
                    primary_category = category
                    primary_score = score
                elif score >= primary_score * 0.5:
                    secondary_categories.append({
                        "category": category,
                        "name": BENEFIT_CATEGORIES[category]["name"],
                        "score": score
                    })

        if primary_category is None:
            return {
                "success": True,
                "primary_category": None,
                "confidence": "low",
                "message": "Unable to classify benefit - insufficient information",
                "suggested_categories": []
            }

        # Determine confidence level
        if primary_score >= 3.0:
            confidence = "high"
        elif primary_score >= 1.5:
            confidence = "medium"
        else:
            confidence = "low"

        return {
            "success": True,
            "primary_category": {
                "code": primary_category,
                "name": BENEFIT_CATEGORIES[primary_category]["name"],
                "description": BENEFIT_CATEGORIES[primary_category]["description"],
                "score": primary_score
            },
            "confidence": confidence,
            "evidence": evidence[primary_category],
            "secondary_categories": secondary_categories[:3],  # Top 3 secondary
            "all_scores": {k: v for k, v in sorted_categories if v > 0}
        }
