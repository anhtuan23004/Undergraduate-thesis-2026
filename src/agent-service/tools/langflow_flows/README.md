# Langflow Flows as Agent Tools

This directory contains workflows exported from [Langflow](https://github.com/langflow-ai/langflow) that are used as tools by the Agent Service.

## Architecture

```
Langflow Designer (UI)
       │
       │ Export as Python
       ▼
┌──────────────────────┐
│  Exported Flow File  │  ← You are here
│  (fraud_detection.py)│
└──────────┬───────────┘
           │
           │ Wrapped by
           ▼
┌──────────────────────┐
│  LangflowTool        │  ← langflow_tool.py
│  (BaseTool wrapper)  │
└──────────┬───────────┘
           │
           │ Registered in
           ▼
┌──────────────────────┐
│  ToolRegistry        │  ← registry.py
└──────────┬───────────┘
           │
           │ Called by
           ▼
┌──────────────────────┐
│  ReAct Agent         │  ← Agent decides to use tool
└──────────────────────┘
```

## Adding a New Langflow Flow

### Step 1: Design in Langflow

1. Open Langflow UI at http://localhost:7860
2. Create your workflow (e.g., "Coverage Validator")
3. Test in Playground
4. Export as Python code:
   - Click **Export** → **Download as Python**
   - Or manually extract the logic

### Step 2: Create Flow File

Create a new Python file in this directory:

```python
# coverage_validator.py

class CoverageValidatorFlow:
    """Validate coverage rules."""

    async def run(self, claim_data: dict) -> dict:
        # Your validation logic here
        return {
            "is_valid": True,
            "errors": [],
            "recommendation": "Approve"
        }
```

### Step 3: Update `__init__.py`

```python
from .fraud_detection import FraudDetectionFlow
from .coverage_validator import CoverageValidatorFlow

__all__ = ["FraudDetectionFlow", "CoverageValidatorFlow"]
```

### Step 4: Create Tool Wrapper

Add to `langflow_tool.py`:

```python
from tools.langflow_flows import CoverageValidatorFlow

class CoverageValidatorTool(BaseTool):
    """Validate coverage rules."""

    def __init__(self):
        self.flow = CoverageValidatorFlow()

    @property
    def name(self) -> str:
        return "coverage_validator"

    async def arun(self, claim_id: str, **kwargs) -> dict:
        result = await self.flow.run(kwargs)
        return {
            "tool": self.name,
            "status": "success",
            "result": result
        }
```

### Step 5: Register Tool

Update `registry.py`:

```python
from tools.langflow_tool import FraudDetectionTool, CoverageValidatorTool

def register_defaults(self) -> None:
    self.register(FraudDetectionTool())
    self.register(CoverageValidatorTool())  # Add this
```

### Step 6: Restart Agent Service

```bash
docker-compose restart agent-service
```

## Existing Flows

| Flow | File | Description |
|------|------|-------------|
| Fraud Detection | `fraud_detection.py` | Checks for fraud indicators |

## Flow Structure

Every flow should follow this structure:

```python
class MyFlow:
    """Docstring describing the flow."""

    def __init__(self):
        # Initialize
        pass

    async def run(self, claim_data: dict) -> dict:
        """Execute the flow.

        Args:
            claim_data: Input data

        Returns:
            Result dictionary
        """
        # Logic here
        return {
            "status": "success",
            "data": {}
        }
```

## Testing

Test your flow directly:

```bash
cd src/agent-service
python -m tools.langflow_flows.example_usage
```

Or test via the agent API:

```bash
curl -X POST http://localhost:8003/api/v1/agent/decide \
  -H "Content-Type: application/json" \
  -d '{
    "claim_id": "TEST-001",
    "extracted_data": {...},
    "policy_number": "POL-001"
  }'
```

## Best Practices

1. **Keep flows simple** - Each flow should do one thing well
2. **Add docstrings** - Help the LLM understand when to use the tool
3. **Handle errors** - Return `status: "error"` on failure
4. **Log important events** - Use `structlog` for debugging
5. **Test independently** - Test flow before integrating with agent

## Troubleshooting

### Tool not found
- Check `registry.py` imports
- Verify flow is in `__init__.py`
- Restart agent service

### Import errors
- Ensure `__init__.py` exists in all directories
- Check Python path includes `src/agent-service`

### Flow returns wrong format
- Must return a dictionary
- Include `status` field
- Wrap result in `result` field
