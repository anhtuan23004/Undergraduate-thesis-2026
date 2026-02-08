"""
Langflow Flows package.

This package contains Python-exported flows from Langflow.
Each flow is a self-contained module that can be run independently
or wrapped as a tool in the agent service.

Available flows:
- fraud_detection: Fraud detection analysis for insurance claims
"""

from .fraud_detection import (
    FraudDetectionFlow,
    FraudDetectionInput,
    FraudDetectionOutput,
    run_fraud_detection,
)

__all__ = [
    "FraudDetectionFlow",
    "FraudDetectionInput",
    "FraudDetectionOutput",
    "run_fraud_detection",
]
