"""Agent Factory for creating LangChain v1 agents.

Handles tool management and agent node creation for LangGraph workflows.
"""

import json
import structlog
from typing import Any, Dict, List, Optional, Callable

from langchain_core.runnables import Runnable
from langchain_core.tools import BaseTool as LangChainBaseTool

from tools import extract_document, load_skill, lookup_icd, search_medicine

logger = structlog.get_logger()


class AgentFactory:
    """Factory for creating agents with middleware.

    Attributes:
        config_loader: Component for loading agent/tool configs.
        llm_client: Client for LLM interactions.
        middleware_config: Shared middleware configuration.
    """

    def __init__(
        self,
        config_loader: Any,
        llm_client: Any,
        middleware_config: Optional[Any] = None,
    ):
        self.config_loader = config_loader
        self.llm_client = llm_client
        self.middleware_config = middleware_config

    def create_base_tools(self, tool_names: List[str]) -> List[LangChainBaseTool]:
        """Get LangChain tool instances by name."""
        tool_map = {
            "extract_documents": extract_document,
            "load_skill": load_skill,
            "lookup_icd": lookup_icd,
            "search_medicine": search_medicine,
        }
        tools = []
        for name in tool_names:
            tool = tool_map.get(name)
            if tool:
                tools.append(tool)
            else:
                logger.warning(f"Tool {name} not found in tool map")
        return tools

    def create_agent_with_state(
        self,
        agent_config_name: str,
        instructions_name: str,
        agent_name: str = "Agent",
    ) -> Callable:
        """Create a stateful agent node for LangGraph.

        Args:
            agent_config_name: Name of the agent YAML config file.
            instructions_name: Name of the instruction Markdown file.
            agent_name: Display name for logging/tracing.

        Returns:
            An async function (node) compatible with LangGraph.
        """
        # Load configurations
        config = self.config_loader.load_agent(agent_config_name)
        tool_names = config.get("tools", [])
        system_prompt = self.config_loader.load_instructions(instructions_name)

        # Get LangChain tools directly
        tools = self.create_base_tools(tool_names)

        async def agent_node(state: Dict[str, Any]) -> Dict[str, Any]:
            """The actual node function executed by LangGraph."""
            logger.info(f"Executing agent node: {agent_name}")

            # Prepare prompt from state
            prompt = self._build_prompt_from_state(state, agent_name)

            # Execute with LLM client using tools
            result = await self.llm_client.generate_with_tools(
                prompt=prompt,
                tools=tools,
                system_prompt=system_prompt,
                output_schema=config.get("output_schema", {}),
            )

            # Format history entry
            history_entry = {
                "agent": agent_name,
                "prompt": prompt[:200] + "...",
                "result": result,
                "step": state.get("current_step", "unknown"),
            }

            return {
                "agent_result": result,
                "history": state.get("history", []) + [history_entry],
                "current_step": f"completed_{agent_config_name}",
            }

        return agent_node

    def _build_prompt_from_state(
        self, state: Dict[str, Any], agent_name: str
    ) -> str:
        """Build prompt using state data.

        This should be overridden or extended by specific agent definitions.
        """
        claim_id = state.get("claim_id", "N/A")
        policy_number = state.get("policy_number", "N/A")
        input_file = state.get("input_file", "N/A")

        return f"""Process insurance claim {claim_id} for policy {policy_number}.
Document source: {input_file}

Recent history:
{json.dumps(state.get('history', [])[-2:], indent=2)}
"""


def get_agent_factory(
    config_loader: Any,
    llm_client: Any,
    middleware_config: Optional[Any] = None,
) -> AgentFactory:
    """Singleton-like getter for AgentFactory."""
    return AgentFactory(config_loader, llm_client, middleware_config)
