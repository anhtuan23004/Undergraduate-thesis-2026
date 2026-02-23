"""Validate consistency tool for claim data validation.

This module provides a tool for validating consistency across claim fields,
ensuring that data from different sources (OCR, forms, databases) aligns.
"""

from typing import Any, Dict, List, Optional

from tools.base import BaseTool


class ValidateConsistencyTool(BaseTool):
    """Tool for validating consistency across claim data fields.

    Validates that extracted data from different sources (invoices, medical records,
    prescriptions) is consistent and matches expected formats and relationships.
    """

    name = "validate_consistency"
    description = (
        "Validate consistency across claim data fields from different sources. "
        "Checks that patient info, dates, amounts, and provider details match "
        "across invoices, medical records, and prescriptions."
    )
    parameters: Dict[str, Any] = {
        "type": "object",
        "properties": {
            "patient_name": {
                "type": "string",
                "description": "Patient name from primary document"
            },
            "patient_id": {
                "type": "string",
                "description": "Patient ID or insurance number"
            },
            "policy_number": {
                "type": "string",
                "description": "Insurance policy number"
            },
            "claim_amount": {
                "type": "number",
                "description": "Total claim amount"
            },
            "service_date": {
                "type": "string",
                "description": "Date of service (ISO format: YYYY-MM-DD)"
            },
            "provider_name": {
                "type": "string",
                "description": "Healthcare provider name"
            },
            "documents": {
                "type": "array",
                "description": "List of extracted documents to cross-validate",
                "items": {
                    "type": "object",
                    "properties": {
                        "doc_type": {
                            "type": "string",
                            "enum": ["invoice", "medical_record", "prescription", "receipt"]
                        },
                        "patient_name": {"type": "string"},
                        "patient_id": {"type": "string"},
                        "amount": {"type": "number"},
                        "date": {"type": "string"},
                        "provider": {"type": "string"}
                    }
                }
            }
        },
        "required": ["patient_name", "policy_number"]
    }

    async def execute(
        self,
        patient_name: str,
        policy_number: str,
        patient_id: Optional[str] = None,
        claim_amount: Optional[float] = None,
        service_date: Optional[str] = None,
        provider_name: Optional[str] = None,
        documents: Optional[List[Dict[str, Any]]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Execute consistency validation.

        Args:
            patient_name: Patient name from primary document
            policy_number: Insurance policy number
            patient_id: Patient ID or insurance number
            claim_amount: Total claim amount
            service_date: Date of service (ISO format)
            provider_name: Healthcare provider name
            documents: List of documents to cross-validate

        Returns:
            Dictionary with validation results including issues list with severity levels
        """
        issues: List[Dict[str, Any]] = []
        warnings: List[Dict[str, Any]] = []

        # Validate patient name consistency across documents
        if documents:
            patient_names = [
                doc.get("patient_name", "").strip().lower()
                for doc in documents
                if doc.get("patient_name")
            ]
            if patient_names and not all(name == patient_names[0] for name in patient_names):
                issues.append({
                    "field": "patient_name",
                    "severity": "high",
                    "message": "Patient name mismatch across documents",
                    "details": {
                        "expected": patient_name,
                        "found": list(set(patient_names))
                    }
                })

        # Validate patient ID format (Vietnamese insurance format)
        if patient_id:
            if not self._is_valid_patient_id(patient_id):
                issues.append({
                    "field": "patient_id",
                    "severity": "medium",
                    "message": "Patient ID format appears invalid",
                    "details": {"value": patient_id}
                })

        # Validate policy number format
        if not self._is_valid_policy_number(policy_number):
            issues.append({
                "field": "policy_number",
                "severity": "high",
                "message": "Policy number format is invalid",
                "details": {"value": policy_number}
                })

        # Validate claim amount is positive and reasonable
        if claim_amount is not None:
            if claim_amount <= 0:
                issues.append({
                    "field": "claim_amount",
                    "severity": "high",
                    "message": "Claim amount must be positive",
                    "details": {"value": claim_amount}
                })
            elif claim_amount > 1_000_000_000:  # 1 billion VND threshold
                warnings.append({
                    "field": "claim_amount",
                    "severity": "low",
                    "message": "Claim amount exceeds typical threshold, requires review",
                    "details": {"value": claim_amount, "threshold": 1_000_000_000}
                })

        # Validate service date is not in the future
        if service_date:
            date_issue = self._validate_date(service_date)
            if date_issue:
                issues.append(date_issue)

        # Cross-validate document amounts sum to claim amount
        if documents and claim_amount is not None:
            total_doc_amount = sum(
                doc.get("amount", 0) or 0 for doc in documents
            )
            if abs(total_doc_amount - claim_amount) > 0.01:  # Allow small rounding differences
                issues.append({
                    "field": "claim_amount",
                    "severity": "high",
                    "message": "Document amounts do not sum to claimed total",
                    "details": {
                        "claimed_total": claim_amount,
                        "documents_total": total_doc_amount,
                        "difference": abs(total_doc_amount - claim_amount)
                    }
                })

        # Check for missing critical fields in documents
        if documents:
            for idx, doc in enumerate(documents):
                missing = []
                if not doc.get("patient_name"):
                    missing.append("patient_name")
                if not doc.get("date"):
                    missing.append("date")
                if doc.get("doc_type") == "invoice" and not doc.get("amount"):
                    missing.append("amount")

                if missing:
                    warnings.append({
                        "field": f"document_{idx}",
                        "severity": "low",
                        "message": f"Document missing recommended fields: {', '.join(missing)}",
                        "details": {"doc_type": doc.get("doc_type"), "missing": missing}
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
            "summary": self._generate_summary(all_issues, len(issues) == 0)
        }

    def _is_valid_patient_id(self, patient_id: str) -> bool:
        """Validate patient ID format."""
        # Vietnamese health insurance numbers are typically 10-15 digits
        cleaned = patient_id.replace(" ", "").replace("-", "")
        return len(cleaned) >= 8 and cleaned.isdigit()

    def _is_valid_policy_number(self, policy_number: str) -> bool:
        """Validate policy number format."""
        # Policy numbers typically follow pattern like POL-XXX or similar
        if not policy_number:
            return False
        cleaned = policy_number.strip()
        return len(cleaned) >= 3

    def _validate_date(self, date_str: str) -> Optional[Dict[str, Any]]:
        """Validate date string and return issue if invalid."""
        from datetime import datetime

        try:
            date = datetime.strptime(date_str, "%Y-%m-%d")
            from datetime import date as date_module
            if date.date() > date_module.today():
                return {
                    "field": "service_date",
                    "severity": "high",
                    "message": "Service date is in the future",
                    "details": {"value": date_str}
                }
        except ValueError:
            return {
                "field": "service_date",
                "severity": "medium",
                "message": "Invalid date format. Expected YYYY-MM-DD",
                "details": {"value": date_str}
            }
        return None

    def _calculate_severity_score(self, issues: List[Dict[str, Any]]) -> float:
        """Calculate overall severity score from 0.0 (clean) to 1.0 (critical)."""
        if not issues:
            return 0.0

        weights = {"high": 1.0, "medium": 0.5, "low": 0.2}
        total_weight = sum(weights.get(issue["severity"], 0.5) for issue in issues)
        return min(1.0, total_weight / 5.0)  # Cap at 1.0, normalize by 5 issues

    def _generate_summary(self, issues: List[Dict[str, Any]], is_valid: bool) -> str:
        """Generate human-readable summary of validation results."""
        if not issues:
            return "All consistency checks passed"

        high_count = sum(1 for i in issues if i["severity"] == "high")
        medium_count = sum(1 for i in issues if i["severity"] == "medium")
        low_count = sum(1 for i in issues if i["severity"] == "low")

        parts = []
        if high_count > 0:
            parts.append(f"{high_count} error(s)")
        if medium_count > 0:
            parts.append(f"{medium_count} warning(s)")
        if low_count > 0:
            parts.append(f"{low_count} note(s)")

        status = "passed" if is_valid else "failed"
        return f"Validation {status}: {', '.join(parts)}"
