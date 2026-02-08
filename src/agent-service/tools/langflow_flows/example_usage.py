"""Example: Using Langflow-exported flows as tools in the Agent.

This file demonstrates how the fraud detection flow is called by the agent
during the ReAct loop.

Workflow in the ReAct agent:
1. Agent observes claim data
2. Agent thinks: "Should I check for fraud?"
3. Agent decides to call fraud_detection tool
4. Tool returns risk score and recommendation
5. Agent uses this information in final decision
"""
import asyncio

# Example 1: Direct usage
async def direct_usage():
    """Use the flow directly (like Langflow would)."""
    from fraud_detection import FraudDetectionFlow

    flow = FraudDetectionFlow()

    result = await flow.run({
        "claim_id": "CLM-001",
        "amount": 15_000_000,
        "hospital": "Bệnh viện Chợ Rẫy",
        "diagnosis_codes": ["J18.9"],
        "description": "Urgent hospitalization"
    })

    print("Risk Score:", result["risk_score"])
    print("Flags:", result["flags"])
    print("Recommendation:", result["recommendation"])


# Example 2: As Agent Tool
async def as_agent_tool():
    """Use as an agent tool (integrated with ReAct)."""
    from tools.langflow_tool import FraudDetectionTool

    tool = FraudDetectionTool()

    result = await tool.arun(
        claim_id="CLM-002",
        amount=25_000_000,
        hospital="Bệnh viện Bạch Mai",
        diagnosis_codes=["I10", "E11.9"],
        description="Emergency surgery"
    )

    print("Tool Result:")
    print(f"  Status: {result['status']}")
    print(f"  Summary: {result['summary']}")
    print(f"  Risk Score: {result['result']['risk_score']}")


# Example 3: ReAct Agent Flow
async def react_agent_example():
    """How the agent uses it during ReAct loop."""
    from tools.registry import get_registry

    registry = get_registry()

    # Agent thinks it needs to check for fraud
    print("Agent: 'I should check for fraud indicators...'")

    # Get the tool
    fraud_tool = registry.get("fraud_detection")

    # Execute
    result = await fraud_tool.arun(
        claim_id="CLM-003",
        amount=50_000_000,  # Very high amount!
        hospital="Local Clinic",
        description="ASAP payment needed"
    )

    # Agent uses result
    if result["result"]["risk_score"] > 0.5:
        print("Agent: 'High fraud risk detected! I should recommend manual review.'")
    else:
        print("Agent: 'Low fraud risk. Proceed with standard processing.'")


if __name__ == "__main__":
    print("=" * 60)
    print("Example 1: Direct Flow Usage")
    print("=" * 60)
    asyncio.run(direct_usage())

    print("\n" + "=" * 60)
    print("Example 2: As Agent Tool")
    print("=" * 60)
    asyncio.run(as_agent_tool())

    print("\n" + "=" * 60)
    print("Example 3: ReAct Agent Integration")
    print("=" * 60)
    asyncio.run(react_agent_example())
