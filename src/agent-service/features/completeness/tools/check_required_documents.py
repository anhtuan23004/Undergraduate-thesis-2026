"""Required documents check tool.

This module provides a tool for verifying that all required documents
are present for a claim based on benefit type and claim characteristics.
"""

from typing import Any, Dict, List, Optional

from core.base.tool import BaseTool


# Required documents by benefit category
REQUIRED_DOCUMENTS = {
    "inpatient": {
        "mandatory": [
            "medical_invoice",
            "medical_record",
            "discharge_summary"
        ],
        "optional": [
            "prescription",
            "lab_results",
            "imaging_reports"
        ]
    },
    "outpatient": {
        "mandatory": [
            "medical_invoice",
            "medical_record"
        ],
        "optional": [
            "prescription",
            "lab_results",
            "referral_letter"
        ]
    },
    "emergency": {
        "mandatory": [
            "medical_invoice",
            "emergency_record",
            "treatment_summary"
        ],
        "optional": [
            "ambulance_receipt",
            "lab_results",
            "imaging_reports"
        ]
    },
    "surgery": {
        "mandatory": [
            "medical_invoice",
            "surgical_report",
            "anesthesia_record",
            "medical_record"
        ],
        "optional": [
            "pre_op_assessment",
            "post_op_summary",
            "pathology_report"
        ]
    },
    "medication": {
        "mandatory": [
            "pharmacy_receipt",
            "prescription"
        ],
        "optional": [
            "medical_record",
            "doctor_letter"
        ]
    },
    "diagnostic": {
        "mandatory": [
            "diagnostic_invoice",
            "test_results"
        ],
        "optional": [
            "referral_letter",
            "medical_record"
        ]
    },
    "dental": {
        "mandatory": [
            "dental_invoice",
            "dental_record"
        ],
        "optional": [
            "x_ray",
            "treatment_plan"
        ]
    },
    "maternity": {
        "mandatory": [
            "medical_invoice",
            "birth_certificate",
            "medical_record",
            "discharge_summary"
        ],
        "optional": [
            "prenatal_records",
            "ultrasound_reports"
        ]
    },
    "mental_health": {
        "mandatory": [
            "medical_invoice",
            "psychiatric_evaluation",
            "treatment_plan"
        ],
        "optional": [
            "therapy_notes",
            "medication_list"
        ]
    },
    "rehabilitation": {
        "mandatory": [
            "medical_invoice",
            "rehabilitation_plan",
            "progress_reports"
        ],
        "optional": [
            "referral_letter",
            "functional_assessment"
        ]
    }
}

# Document type definitions with validation rules
DOCUMENT_TYPES = {
    "medical_invoice": {
        "name": "Medical Invoice",
        "description": "Itemized bill from healthcare provider",
        "required_fields": ["provider_name", "total_amount", "date"],
        "keywords": ["invoice", "bill", "receipt", "hóa đơn"]
    },
    "medical_record": {
        "name": "Medical Record",
        "description": "Clinical documentation of patient encounter",
        "required_fields": ["patient_name", "diagnosis", "date"],
        "keywords": ["medical record", "clinical notes", "bệnh án"]
    },
    "discharge_summary": {
        "name": "Discharge Summary",
        "description": "Summary of hospital stay and discharge instructions",
        "required_fields": ["admission_date", "discharge_date", "diagnosis"],
        "keywords": ["discharge", "summary", "xuất viện"]
    },
    "prescription": {
        "name": "Prescription",
        "description": "Medication prescription from doctor",
        "required_fields": ["medication_name", "dosage", "doctor_name"],
        "keywords": ["prescription", "đơn thuốc", "Rx"]
    },
    "lab_results": {
        "name": "Laboratory Results",
        "description": "Blood tests, urinalysis, or other lab reports",
        "required_fields": ["test_type", "result", "date"],
        "keywords": ["lab", "laboratory", "blood test", "xét nghiệm"]
    },
    "imaging_reports": {
        "name": "Imaging Reports",
        "description": "X-ray, MRI, CT scan, or ultrasound reports",
        "required_fields": ["imaging_type", "findings", "date"],
        "keywords": ["x-ray", "MRI", "CT scan", "ultrasound", "chẩn đoán hình ảnh"]
    },
    "emergency_record": {
        "name": "Emergency Department Record",
        "description": "Documentation from emergency room visit",
        "required_fields": ["arrival_time", "chief_complaint", "treatment"],
        "keywords": ["emergency", "ER", "cấp cứu"]
    },
    "surgical_report": {
        "name": "Surgical Report",
        "description": "Detailed report of surgical procedure",
        "required_fields": ["procedure_name", "surgeon", "date"],
        "keywords": ["surgery", "operation", "surgical", "phẫu thuật"]
    },
    "pharmacy_receipt": {
        "name": "Pharmacy Receipt",
        "description": "Receipt from pharmacy for medications",
        "required_fields": ["pharmacy_name", "medication", "amount"],
        "keywords": ["pharmacy", "receipt", "nhà thuốc"]
    },
    "birth_certificate": {
        "name": "Birth Certificate",
        "description": "Official birth documentation for maternity claims",
        "required_fields": ["baby_name", "birth_date", "birth_weight"],
        "keywords": ["birth", "giấy khai sinh", "newborn"]
    }
}


class CheckRequiredDocumentsTool(BaseTool):
    """Tool for checking required documents for a claim.

    Verifies that all mandatory documents are present based on the
    benefit type and claim characteristics.
    """

    name = "check_required_documents"
    description = (
        "Verify that all required documents are present for a claim based on "
        "benefit type (inpatient, outpatient, surgery, etc.). Checks for "
        "mandatory and optional documents, identifies missing items."
    )
    parameters: Dict[str, Any] = {
        "type": "object",
        "properties": {
            "benefit_category": {
                "type": "string",
                "enum": list(REQUIRED_DOCUMENTS.keys()),
                "description": "Benefit category to check requirements for"
            },
            "submitted_documents": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "document_type": {
                            "type": "string",
                            "description": "Type of document"
                        },
                        "document_name": {
                            "type": "string",
                            "description": "Name or title of the document"
                        },
                        "extracted_data": {
                            "type": "object",
                            "description": "Structured data extracted from the document"
                        }
                    }
                },
                "description": "List of documents already submitted with the claim"
            },
            "claim_amount": {
                "type": "number",
                "description": "Total claim amount for threshold-based requirements"
            },
            "hospital_stay_days": {
                "type": "number",
                "description": "Number of days in hospital if applicable"
            }
        },
        "required": ["benefit_category", "submitted_documents"]
    }

    async def execute(
        self,
        benefit_category: str,
        submitted_documents: List[Dict[str, Any]],
        claim_amount: Optional[float] = None,
        hospital_stay_days: Optional[int] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Execute required documents check.

        Args:
            benefit_category: Type of benefit being claimed
            submitted_documents: List of documents already submitted
            claim_amount: Total claim amount
            hospital_stay_days: Length of hospital stay

        Returns:
            Dictionary with document verification results
        """
        # Normalize benefit category
        category = self._normalize_string(benefit_category).strip()

        if category not in REQUIRED_DOCUMENTS:
            return {
                "success": False,
                "error": f"Unknown benefit category: {benefit_category}",
                "valid_categories": list(REQUIRED_DOCUMENTS.keys())
            }

        requirements = REQUIRED_DOCUMENTS[category]
        submitted_types = set()

        # Extract document types from submitted documents
        for doc in submitted_documents:
            doc_type = self._normalize_string(doc.get("document_type", "")).strip()
            # Map common variations to standard types
            mapped_type = self._map_document_type(doc_type)
            if mapped_type:
                submitted_types.add(mapped_type)

        # Check mandatory documents
        missing_mandatory = []
        present_mandatory = []

        for doc_type in requirements["mandatory"]:
            if doc_type in submitted_types:
                present_mandatory.append({
                    "type": doc_type,
                    "name": DOCUMENT_TYPES.get(doc_type, {}).get("name", doc_type),
                    "status": "present"
                })
            else:
                missing_mandatory.append({
                    "type": doc_type,
                    "name": DOCUMENT_TYPES.get(doc_type, {}).get("name", doc_type),
                    "description": DOCUMENT_TYPES.get(doc_type, {}).get("description", ""),
                    "required_fields": DOCUMENT_TYPES.get(doc_type, {}).get("required_fields", []),
                    "status": "missing"
                })

        # Check optional documents
        present_optional = []
        missing_optional = []

        for doc_type in requirements["optional"]:
            if doc_type in submitted_types:
                present_optional.append({
                    "type": doc_type,
                    "name": DOCUMENT_TYPES.get(doc_type, {}).get("name", doc_type),
                    "status": "present"
                })
            else:
                missing_optional.append({
                    "type": doc_type,
                    "name": DOCUMENT_TYPES.get(doc_type, {}).get("name", doc_type),
                    "description": DOCUMENT_TYPES.get(doc_type, {}).get("description", ""),
                    "status": "missing"
                })

        # Determine overall status
        if missing_mandatory:
            status = "incomplete"
            completeness = len(present_mandatory) / (len(present_mandatory) + len(missing_mandatory))
        else:
            status = "complete"
            completeness = 1.0

        # Build result
        result = {
            "success": True,
            "benefit_category": benefit_category,
            "status": status,
            "completeness_ratio": round(completeness, 2),
            "mandatory_documents": {
                "present": present_mandatory,
                "missing": missing_mandatory,
                "total_required": len(requirements["mandatory"]),
                "total_present": len(present_mandatory)
            },
            "optional_documents": {
                "present": present_optional,
                "missing": missing_optional,
                "total_present": len(present_optional)
            },
            "summary": self._generate_summary(
                status, missing_mandatory, present_mandatory, present_optional
            )
        }

        # Add recommendations for missing documents
        if missing_mandatory:
            result["recommendations"] = [
                f"Submit {doc['name']} ({doc['type']})"
                for doc in missing_mandatory
            ]

        return result

    def _map_document_type(self, doc_type: str) -> Optional[str]:
        """Map document type variations to standard types.

        Args:
            doc_type: Document type string to map

        Returns:
            Standard document type or None if not recognized
        """
        doc_type_lower = doc_type.lower()

        # Direct match
        if doc_type_lower in DOCUMENT_TYPES:
            return doc_type_lower

        # Keyword matching
        for standard_type, info in DOCUMENT_TYPES.items():
            if doc_type_lower == standard_type.lower():
                return standard_type
            for keyword in info.get("keywords", []):
                if keyword.lower() in doc_type_lower:
                    return standard_type

        # Common variations
        variations = {
            "invoice": "medical_invoice",
            "bill": "medical_invoice",
            "receipt": "medical_invoice",
            "hóa đơn": "medical_invoice",
            "medical report": "medical_record",
            "bệnh án": "medical_record",
            "giấy ra viện": "discharge_summary",
            "xuất viện": "discharge_summary",
            "đơn thuốc": "prescription",
            "xét nghiệm": "lab_results",
            "x-quang": "imaging_reports",
            "ct": "imaging_reports",
            "mri": "imaging_reports",
            "cấp cứu": "emergency_record",
            "phẫu thuật": "surgical_report",
            "giấy khai sinh": "birth_certificate"
        }

        for variation, standard in variations.items():
            if variation in doc_type_lower:
                return standard

        return None

    def _generate_summary(
        self,
        status: str,
        missing_mandatory: List[Dict],
        present_mandatory: List[Dict],
        present_optional: List[Dict]
    ) -> str:
        """Generate human-readable summary of document check.

        Args:
            status: Overall status (complete/incomplete)
            missing_mandatory: List of missing mandatory documents
            present_mandatory: List of present mandatory documents
            present_optional: List of present optional documents

        Returns:
            Summary string
        """
        if status == "complete":
            summary = (
                f"All {len(present_mandatory)} required documents are present. "
            )
            if present_optional:
                summary += f"Additionally, {len(present_optional)} optional documents were submitted."
            return summary
        else:
            missing_names = [doc["name"] for doc in missing_mandatory]
            return (
                f"Missing {len(missing_mandatory)} required document(s): "
                f"{', '.join(missing_names)}. "
                f"{len(present_mandatory)} of {len(present_mandatory) + len(missing_mandatory)} "
                f"mandatory documents are present."
            )
