"""
Langflow Tool Wrapper

This module provides a base wrapper for running Langflow-exported flows as tools
in the agent service. It handles input/output formatting, error handling, and
integration with the agent's tool system.

Usage:
    1. Export flow from Langflow as Python code
    2. Place the exported file in langflow_flows/ directory
    3. Create a tool class that extends LangflowToolWrapper
    4. Register the tool in registry.py
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Type, Optional
from pydantic import BaseModel, Field
import logging

# Configure logging
logger = logging.getLogger(__name__)


class LangflowToolInput(BaseModel):
    """Base input schema for Langflow tools."""
    input_data: Dict[str, Any] = Field(
        ...,
        description="Input data to pass to the Langflow flow"
    )


class LangflowToolOutput(BaseModel):
    """Base output schema for Langflow tools."""
    status: str = Field(..., description="Status of the flow execution")
    result: Dict[str, Any] = Field(default_factory=dict, description="Flow output data")
    error: Optional[str] = Field(None, description="Error message if execution failed")


class BaseTool(ABC):
    """
    Abstract base class for all tools in the agent service.

    This matches the pattern used by other tools in the system.
    """

    name: str
    description: str
    input_schema: Type[BaseModel]
    output_schema: Type[BaseModel]

    @abstractmethod
    async def execute(self, **kwargs) -> Dict[str, Any]:
        """Execute the tool with the given parameters."""
        pass

    def get_schema(self) -> Dict[str, Any]:
        """Get the tool's schema for agent consumption."""
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_schema.model_json_schema(),
            "output_schema": self.output_schema.model_json_schema(),
        }


class LangflowToolWrapper(BaseTool):
    """
    Wrapper for Langflow-exported Python flows.

    This wrapper provides:
    - Standardized input/output formatting
    - Error handling and logging
    - Integration with agent tool system
    - Async execution support

    To use:
        1. Subclass this wrapper
        2. Set the `flow_class` attribute to your exported flow class
        3. Define appropriate name, description, and schemas
    """

    # Override these in subclasses
    name: str = "langflow_tool"
    description: str = "Base wrapper for Langflow flows"
    input_schema: Type[BaseModel] = LangflowToolInput
    output_schema: Type[BaseModel] = LangflowToolOutput

    # Set this to the exported flow class
    flow_class: Optional[Type] = None

    def __init__(self):
        """Initialize the tool wrapper."""
        if self.flow_class is None:
            raise ValueError(f"{self.__class__.__name__} must set flow_class attribute")
        self._flow_instance = None

    def _get_flow_instance(self):
        """Get or create the flow instance (lazy initialization)."""
        if self._flow_instance is None:
            self._flow_instance = self.flow_class()
        return self._flow_instance

    async def execute(self, **kwargs) -> Dict[str, Any]:
        """
        Execute the wrapped Langflow flow.

        Args:
            **kwargs: Input parameters for the flow

        Returns:
            Dictionary with execution results
        """
        try:
            # Extract input data
            input_data = kwargs.get("input_data") or kwargs

            # Validate input if schema is defined
            if hasattr(self, 'input_schema') and self.input_schema != LangflowToolInput:
                validated_input = self.input_schema(**input_data)
                input_data = validated_input.model_dump()

            # Execute the flow
            logger.info(f"Executing {self.name} with input: {input_data}")
            flow = self._get_flow_instance()

            # Langflow exported flows typically have a 'run' method
            if hasattr(flow, 'run'):
                result = await flow.run(input_data)
            # Or a direct __call__ method
            elif hasattr(flow, '__call__'):
                result = await flow(input_data)
            else:
                raise ValueError(f"Flow class {self.flow_class.__name__} has no run or __call__ method")

            # Format output - merge flow result with status
            output = {
                "status": "success",
                "error": None,
                **result,  # Merge flow output fields
            }

            # Validate output if schema is defined
            if hasattr(self, 'output_schema') and self.output_schema != LangflowToolOutput:
                validated_output = self.output_schema(**output)
                output = validated_output.model_dump()

            logger.info(f"{self.name} executed successfully")
            return output

        except Exception as e:
            logger.error(f"Error executing {self.name}: {str(e)}")
            return self._handle_error(e)

    def _handle_error(self, error: Exception) -> Dict[str, Any]:
        """Handle execution errors gracefully."""
        error_output = {
            "status": "error",
            "result": {},
            "error": str(error),
        }

        # Try to validate error output against schema
        try:
            if hasattr(self, 'output_schema'):
                validated = self.output_schema(**error_output)
                return validated.model_dump()
        except Exception:
            pass

        return error_output

    def __call__(self, **kwargs) -> Dict[str, Any]:
        """Allow direct calling of the tool."""
        import asyncio
        return asyncio.run(self.execute(**kwargs))


class FraudDetectionInput(BaseModel):
    """Input schema for fraud detection tool."""
    claim_id: str = Field(..., description="Unique claim identifier")
    patient_name: str = Field(..., description="Patient name")
    total_amount: float = Field(..., description="Total claim amount in VND")
    diagnosis_codes: list = Field(default_factory=list, description="List of ICD-10 codes")
    provider_name: str = Field(..., description="Healthcare provider name")
    submission_date: str = Field(..., description="Claim submission date (ISO format)")
    notes: Optional[str] = Field(None, description="Additional claim notes")
    previous_claims_count: int = Field(0, description="Number of recent claims by patient")
    previous_claims_amount: float = Field(0.0, description="Total amount of recent claims")


class FraudDetectionOutput(BaseModel):
    """Output schema for fraud detection tool."""
    status: str = Field(..., description="Execution status")
    risk_score: float = Field(..., description="Risk score from 0.0 to 1.0")
    risk_level: str = Field(..., description="Risk level: low, medium, high, critical")
    flags: list = Field(default_factory=list, description="List of detected risk flags")
    recommendation: str = Field(..., description="Recommended action")
    details: Dict[str, Any] = Field(default_factory=dict, description="Additional details")
    processed_at: str = Field(..., description="Processing timestamp")
    error: Optional[str] = Field(None, description="Error message if failed")


def create_langflow_tool(
    name: str,
    description: str,
    flow_class: Type,
    input_schema: Type[BaseModel] = LangflowToolInput,
    output_schema: Type[BaseModel] = LangflowToolOutput,
) -> Type[LangflowToolWrapper]:
    """
    Factory function to create a Langflow tool wrapper class dynamically.

    This is useful when you want to create a tool wrapper without defining
    a full subclass.

    Args:
        name: Tool name
        description: Tool description
        flow_class: The exported Langflow flow class
        input_schema: Pydantic model for input validation
        output_schema: Pydantic model for output validation

    Returns:
        A configured LangflowToolWrapper subclass
    """
    return type(
        f"{name}Tool",
        (LangflowToolWrapper,),
        {
            "name": name,
            "description": description,
            "flow_class": flow_class,
            "input_schema": input_schema,
            "output_schema": output_schema,
        },
    )


# Export all public symbols
__all__ = [
    "LangflowToolWrapper",
    "LangflowToolInput",
    "LangflowToolOutput",
    "BaseTool",
    "FraudDetectionInput",
    "FraudDetectionOutput",
    "create_langflow_tool",
]
