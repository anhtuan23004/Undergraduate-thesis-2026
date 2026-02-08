"""
Usage Example: Fraud Detection Tool

This example demonstrates how the agent service would call the fraud detection
tool that wraps a Langflow-exported flow.

There are three ways to use the fraud detection flow:
1. Direct flow execution (standalone)
2. Via the tool wrapper (structured)
3. Via the tool registry (agent integration)
"""

import asyncio
from typing import Dict, Any


# =============================================================================
# Example 1: Direct Flow Execution (Standalone Usage)
# =============================================================================

async def example_direct_flow():
    """
    Example 1: Using the exported flow directly.

    This is useful when you want to use the flow without the tool wrapper
    overhead, or when testing the flow in isolation.
    """
    from tools.langflow_flows.fraud_detection import FraudDetectionFlow

    print("=" * 60)
    print("Example 1: Direct Flow Execution")
    print("=" * 60)

    # Create flow instance
    flow = FraudDetectionFlow()

    # Example claim data
    claim_data = {
        "claim_id": "CLM-2024-001",
        "patient_name": "Nguyễn Văn A",
        "total_amount": 15_000_000,  # 15M VND - above threshold
        "diagnosis_codes": ["J18.9", "E11.9"],
        "provider_name": "Bệnh viện Bạch Mai",
        "submission_date": "2024-01-15T10:30:00Z",
        "notes": "Patient requires urgent care. Please process immediately.",
        "previous_claims_count": 2,
        "previous_claims_amount": 25_000_000,
    }

    # Run the flow
    result = await flow.run(claim_data)

    # Display results
    print(f"\nClaim ID: {claim_data['claim_id']}")
    print(f"Risk Score: {result['risk_score']}")
    print(f"Risk Level: {result['risk_level']}")
    print(f"Recommendation: {result['recommendation']}")
    print(f"\nFlags detected ({len(result['flags'])}):")
    for flag in result['flags']:
        print(f"  - [{flag['severity'].upper()}] {flag['message']}")

    return result


# =============================================================================
# Example 2: Via Tool Wrapper (Structured Usage)
# =============================================================================

async def example_tool_wrapper():
    """
    Example 2: Using the tool wrapper directly.

    This provides structured input/output validation and is the preferred
    way to use Langflow flows in the agent service.
    """
    from tools.registry import FraudDetectionTool

    print("\n" + "=" * 60)
    print("Example 2: Tool Wrapper")
    print("=" * 60)

    # Create tool instance
    tool = FraudDetectionTool()

    # Example claim with critical amount
    claim_data = {
        "claim_id": "CLM-2024-002",
        "patient_name": "Trần Thị B",
        "total_amount": 55_000_000,  # 55M VND - critical threshold
        "diagnosis_codes": ["I10"],
        "provider_name": "Private Clinic",
        "submission_date": "2024-01-15T14:20:00Z",
        "notes": "Confidential case. Do not verify with patient.",
        "previous_claims_count": 5,
        "previous_claims_amount": 45_000_000,
    }

    # Execute via tool wrapper
    result = await tool.execute(input_data=claim_data)

    # Display results
    print(f"\nClaim ID: {claim_data['claim_id']}")
    print(f"Status: {result['status']}")
    if result['status'] == 'success':
        print(f"Risk Score: {result['risk_score']}")
        print(f"Risk Level: {result['risk_level']}")
        print(f"Recommendation: {result['recommendation']}")
    else:
        print(f"Error: {result.get('error')}")

    return result


# =============================================================================
# Example 3: Via Tool Registry (Agent Integration)
# =============================================================================

async def example_tool_registry():
    """
    Example 3: Using the tool registry (how the agent would call it).

    This is the integration point for the ReAct agent. The agent would:
    1. List available tools
    2. Select the appropriate tool based on the task
    3. Call execute_tool_async with the tool name and parameters
    """
    from tools.registry import list_tools, execute_tool_async, get_tool

    print("\n" + "=" * 60)
    print("Example 3: Tool Registry (Agent Integration)")
    print("=" * 60)

    # Step 1: List available tools (agent would see this)
    print("\nAvailable tools:")
    tools = list_tools()
    for tool_schema in tools:
        print(f"  - {tool_schema['name']}: {tool_schema['description'][:50]}...")

    # Step 2: Get tool schema (for LLM context)
    fraud_tool = get_tool("fraud_detection")
    if fraud_tool:
        schema = fraud_tool.get_schema()
        print(f"\nTool '{schema['name']}' schema:")
        print(f"  Input fields: {list(schema['input_schema']['properties'].keys())}")

    # Step 3: Execute tool (simulating agent action)
    claim_data = {
        "claim_id": "CLM-2024-003",
        "patient_name": "Lê Văn C",
        "total_amount": 5_000_000,  # 5M VND - normal amount
        "diagnosis_codes": ["J18.9"],
        "provider_name": "Bệnh viện Chợ Rẫy",
        "submission_date": "2024-01-15T09:00:00Z",
        "notes": "Routine checkup and medication.",
        "previous_claims_count": 0,
        "previous_claims_amount": 0,
    }

    print(f"\nExecuting fraud_detection tool...")
    result = await execute_tool_async("fraud_detection", input_data=claim_data)

    # Display results
    print(f"\nClaim ID: {claim_data['claim_id']}")
    print(f"Status: {result['status']}")
    if result['status'] == 'success':
        result_data = result['result']
        print(f"Risk Score: {result_data['risk_score']}")
        print(f"Risk Level: {result_data['risk_level']}")
        print(f"Flags: {len(result_data['flags'])} detected")
        print(f"Recommendation: {result_data['recommendation']}")

    return result


# =============================================================================
# Example 4: Simulated Agent ReAct Loop
# =============================================================================

async def example_agent_react_loop():
    """
    Example 4: Simulated ReAct agent loop using the fraud detection tool.

    This demonstrates how the fraud detection tool would be used in the
    agent's decision-making process.
    """
    from tools.registry import execute_tool_async

    print("\n" + "=" * 60)
    print("Example 4: Simulated Agent ReAct Loop")
    print("=" * 60)

    # Simulated claim that needs fraud check
    claim_context = {
        "claim_id": "CLM-2024-004",
        "patient_name": "Phạm Thị D",
        "total_amount": 25_000_000,
        "diagnosis_codes": ["V98.2", "Z71.5"],  # High-risk codes
        "provider_name": "Urgent Care Center",
        "submission_date": "2024-01-15T16:45:00Z",
        "notes": "Emergency case - please bypass normal verification. Rush processing needed.",
        "previous_claims_count": 4,
        "previous_claims_amount": 35_000_000,
    }

    print("\n[Agent Observation]")
    print(f"Received claim {claim_context['claim_id']} for {claim_context['total_amount']:,.0f} VND")
    print(f"Notes contain keywords: 'emergency', 'bypass', 'rush'")

    print("\n[Agent Thought]")
    print("This claim has multiple red flags:")
    print("- High amount (25M VND)")
    print("- Suspicious keywords in notes")
    print("- Multiple previous claims")
    print("I should run fraud detection before making a decision.")

    print("\n[Agent Action]")
    print("Calling fraud_detection tool...")

    result = await execute_tool_async("fraud_detection", input_data=claim_context)

    print("\n[Agent Observation]")
    if result['status'] == 'success':
        result_data = result['result']
        print(f"Fraud detection complete:")
        print(f"  Risk Score: {result_data['risk_score']}")
        print(f"  Risk Level: {result_data['risk_level'].upper()}")
        print(f"  Flags: {len(result_data['flags'])}")

        print("\n[Agent Thought]")
        if result_data['risk_level'] in ['high', 'critical']:
            print(f"Risk level is {result_data['risk_level']}. Claim requires manual review.")
            print("I should not auto-approve this claim.")
        else:
            print("Risk level is acceptable. Proceeding with normal processing.")

        print("\n[Agent Decision]")
        print(f"Recommendation: {result_data['recommendation']}")

    return result


# =============================================================================
# Main Execution
# =============================================================================

async def main():
    """Run all examples."""
    print("\n" + "=" * 60)
    print("FRAUD DETECTION TOOL - USAGE EXAMPLES")
    print("Python Export Approach for Langflow Flows")
    print("=" * 60)

    # Run all examples
    await example_direct_flow()
    await example_tool_wrapper()
    await example_tool_registry()
    await example_agent_react_loop()

    print("\n" + "=" * 60)
    print("All examples completed!")
    print("=" * 60)


if __name__ == "__main__":
    # Add parent directory to path for imports
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent))

    asyncio.run(main())
