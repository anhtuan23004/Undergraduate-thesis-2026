"""Fraud Detection Flow - Exported from Langflow.

This module implements a fraud detection workflow that can be used as a tool
by the Agent Service. It performs multiple checks on claim data to identify
potentially fraudulent claims.

Example usage:
    flow = FraudDetectionFlow()
    result = await flow.run({
        "claim_id": "CLM-001",
        "amount": 15000000,
        "hospital": "BV Cho Ray",
        "diagnosis_codes": ["J18.9"],
        "submission_date": "2024-01-15"
    })
"""
from typing import Dict, Any, List
from datetime import datetime


class FraudDetectionFlow:
    """Fraud detection workflow for insurance claims.

    Performs multiple fraud checks:
    1. Amount threshold check
    2. Suspicious keyword detection
    3. Velocity check (claim frequency)
    4. Pattern matching

    Returns a risk score and recommendation.
    """

    def __init__(self):
        """Initialize the fraud detection flow."""
        # Thresholds (VND)
        self.HIGH_AMOUNT_THRESHOLD = 10_000_000
        self.MAX_REASONABLE_AMOUNT = 50_000_000

        # Suspicious keywords
        self.SUSPICIOUS_KEYWORDS = [
            "urgent", "emergency", "asap", "immediately",
            "khẩn cấp", "gấp", "ngay lập tức"
        ]

        # High-risk diagnosis codes
        self.HIGH_RISK_DIAGNOSES = [
            "Z71.1",  # Person encountering health services for other counseling
            "Z76.5",  # Person encountering health services for other reasons
        ]

        # Claim history for velocity check (in-memory, reset on restart)
        self.claim_history: Dict[str, List[datetime]] = {}

    async def run(self, claim_data: Dict[str, Any]) -> Dict[str, Any]:
        """Run the fraud detection flow.

        Args:
            claim_data: Dictionary containing claim information
                - claim_id: Unique claim identifier
                - amount: Claim amount in VND
                - hospital: Hospital name
                - diagnosis_codes: List of ICD-10 codes
                - submission_date: Date of submission (ISO format)
                - description: Optional claim description

        Returns:
            Dictionary with fraud check results:
                - risk_score: Float between 0-1
                - flags: List of triggered flags
                - recommendation: String recommendation
                - details: Detailed check results
        """
        flags = []
        risk_factors = []

        # Check 1: Amount threshold
        amount_check = self._check_amount(claim_data)
        if amount_check["triggered"]:
            flags.append(f"HIGH_AMOUNT: {amount_check['details']}")
            risk_factors.append(0.3)

        # Check 2: Suspicious keywords
        keyword_check = self._check_suspicious_keywords(claim_data)
        if keyword_check["triggered"]:
            flags.append(f"SUSPICIOUS_KEYWORDS: {keyword_check['details']}")
            risk_factors.append(0.25)

        # Check 3: Diagnosis risk
        diagnosis_check = self._check_diagnosis(claim_data)
        if diagnosis_check["triggered"]:
            flags.append(f"HIGH_RISK_DIAGNOSIS: {diagnosis_check['details']}")
            risk_factors.append(0.2)

        # Check 4: Velocity (claim frequency)
        velocity_check = await self._check_velocity(claim_data)
        if velocity_check["triggered"]:
            flags.append(f"HIGH_VELOCITY: {velocity_check['details']}")
            risk_factors.append(0.35)

        # Calculate final risk score
        risk_score = min(sum(risk_factors), 1.0)

        # Generate recommendation
        recommendation = self._generate_recommendation(risk_score, flags)

        return {
            "risk_score": round(risk_score, 2),
            "flags": flags,
            "recommendation": recommendation,
            "details": {
                "amount_check": amount_check,
                "keyword_check": keyword_check,
                "diagnosis_check": diagnosis_check,
                "velocity_check": velocity_check
            }
        }

    def _check_amount(self, claim_data: Dict[str, Any]) -> Dict[str, Any]:
        """Check if claim amount is suspicious."""
        amount = claim_data.get("amount", 0)

        if amount > self.MAX_REASONABLE_AMOUNT:
            return {
                "triggered": True,
                "severity": "HIGH",
                "details": f"Amount {amount:,} VND exceeds maximum reasonable threshold",
                "amount": amount
            }
        elif amount > self.HIGH_AMOUNT_THRESHOLD:
            return {
                "triggered": True,
                "severity": "MEDIUM",
                "details": f"Amount {amount:,} VND is above high threshold",
                "amount": amount
            }

        return {"triggered": False, "amount": amount}

    def _check_suspicious_keywords(self, claim_data: Dict[str, Any]) -> Dict[str, Any]:
        """Check for suspicious keywords in claim."""
        text_to_check = ""

        # Check various fields
        for field in ["description", "notes", "hospital", "remarks"]:
            if field in claim_data and claim_data[field]:
                text_to_check += " " + str(claim_data[field]).lower()

        found_keywords = []
        for keyword in self.SUSPICIOUS_KEYWORDS:
            if keyword.lower() in text_to_check:
                found_keywords.append(keyword)

        if found_keywords:
            return {
                "triggered": True,
                "severity": "MEDIUM",
                "details": f"Found suspicious keywords: {', '.join(found_keywords)}",
                "keywords_found": found_keywords
            }

        return {"triggered": False, "keywords_found": []}

    def _check_diagnosis(self, claim_data: Dict[str, Any]) -> Dict[str, Any]:
        """Check for high-risk diagnosis codes."""
        codes = claim_data.get("diagnosis_codes", [])

        high_risk_found = []
        for code in codes:
            if code in self.HIGH_RISK_DIAGNOSES:
                high_risk_found.append(code)

        if high_risk_found:
            return {
                "triggered": True,
                "severity": "LOW",
                "details": f"High-risk diagnosis codes: {', '.join(high_risk_found)}",
                "codes_found": high_risk_found
            }

        return {"triggered": False, "codes_found": []}

    async def _check_velocity(self, claim_data: Dict[str, Any]) -> Dict[str, Any]:
        """Check claim submission velocity (frequency)."""
        claim_id = claim_data.get("claim_id", "unknown")

        # In real implementation, this would query a database
        # For now, use in-memory tracking
        now = datetime.now()

        if claim_id not in self.claim_history:
            self.claim_history[claim_id] = []

        # Add current claim
        self.claim_history[claim_id].append(now)

        # Count claims in last 30 days
        recent_claims = [
            dt for dt in self.claim_history[claim_id]
            if (now - dt).days <= 30
        ]

        if len(recent_claims) > 5:
            return {
                "triggered": True,
                "severity": "HIGH",
                "details": f"High claim velocity: {len(recent_claims)} claims in 30 days",
                "claims_in_30_days": len(recent_claims)
            }
        elif len(recent_claims) > 3:
            return {
                "triggered": True,
                "severity": "MEDIUM",
                "details": f"Elevated claim frequency: {len(recent_claims)} claims in 30 days",
                "claims_in_30_days": len(recent_claims)
            }

        return {
            "triggered": False,
            "claims_in_30_days": len(recent_claims)
        }

    def _generate_recommendation(self, risk_score: float, flags: List[str]) -> str:
        """Generate recommendation based on risk score."""
        if risk_score >= 0.7:
            return (
                f"HIGH FRAUD RISK (score: {risk_score:.2f}). "
                f"Manual review required. Flags: {len(flags)}"
            )
        elif risk_score >= 0.4:
            return (
                f"MEDIUM FRAUD RISK (score: {risk_score:.2f}). "
                f"Additional verification recommended."
            )
        elif risk_score > 0:
            return (
                f"LOW FRAUD RISK (score: {risk_score:.2f}). "
                f"Standard processing."
            )
        else:
            return "NO FRAUD RISK. Proceed with normal processing."
