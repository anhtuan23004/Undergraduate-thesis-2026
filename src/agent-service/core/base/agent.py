"""SkillAgent base class for skill-driven multi-agent architecture.

Each agent in the system inherits from SkillAgent. The base class:
- Reads the tool list from config/agents/*.yaml (source of truth)
- Instantiates tools via TOOL_REGISTRY
- Loads JSON schemas from config/schemas/*.json for Gemini function-calling
- Loads skill instructions from config/instructions/*.md as LLM system prompt
- Runs the generic agentic loop via LLMClient.generate_with_tools()

Subclasses only need to implement:
  - context_prompt(state) → str
  - run(state) → Dict  (to wrap result in the correct state keys)
"""

import structlog
from typing import Any, Dict, List, Optional

from core.ports.llm_client import LLMClientInterface
from core.ports.config_loader import ConfigLoaderInterface
from workflow.state import GraphState
from core.base.tool_registry import TOOL_REGISTRY

logger = structlog.get_logger()


class SkillAgent:
    """Base class for all skill-driven agents.

    Reads tool list and output schema from agents/*.yaml, loads per-tool
    JSON schemas from schemas/*.json (used as Gemini function-calling
    definitions), and loads the skill instructions from instructions/*.md.

    Attributes:
        config: Parsed agent YAML config dict.
        tools: List of instantiated tool objects (from TOOL_REGISTRY).
        tool_schemas: List of JSON schema dicts for each tool.
        output_schema: Expected output shape for the agent's final JSON.
        instructions: Skill instructions (system prompt) from .md file.
        llm: Shared LLM client instance (via interface).
        config_loader: Configuration loader instance (via interface).
    """

    def __init__(
        self,
        agent_config_name: str,
        instructions_name: str,
        config_loader: ConfigLoaderInterface,
        llm_client: LLMClientInterface
    ) -> None:
        """Initialise SkillAgent from config files.

        Args:
            agent_config_name: Base name of the YAML file in config/agents/
                (e.g. ``"completeness_check_agent"`` for
                ``completeness_check_agent.yaml``).
            instructions_name: Base name of the Markdown file in
                config/instructions/ (e.g. ``"completeness_agent"``).
            config_loader: Implementation of ConfigLoaderInterface for
                loading configurations.
            llm_client: Implementation of LLMClientInterface for
                LLM interactions.
        """
        self.config_loader = config_loader
        self.config: Dict[str, Any] = self.config_loader.load_agent(agent_config_name)

        # Instantiate tools declared in the YAML config
        tool_names: List[str] = self.config.get("tools", [])
        self.tools = []
        self.tool_schemas: List[Dict[str, Any]] = []

        for name in tool_names:
            tool_cls = TOOL_REGISTRY.get(name)
            if tool_cls is None:
                raise ValueError(
                    f"Tool '{name}' declared in {agent_config_name}.yaml "
                    f"is not registered in TOOL_REGISTRY."
                )
            self.tools.append(tool_cls())

            try:
                schema = self.config_loader.load_schema(name)
                self.tool_schemas.append(schema)
            except FileNotFoundError:
                # Schema is optional for function-calling; tool still runs
                pass

        # Output schema drives the final JSON response shape
        self.output_schema: Dict[str, Any] = self.config.get("output_schema", {})

        # Skill instructions become the LLM system prompt
        self.instructions: str = self.config_loader.load_instructions(instructions_name)

        self.llm = llm_client

    def context_prompt(self, state: GraphState) -> str:  # type: ignore[override]
        """Build the task-specific prompt from graph state.

        Subclasses MUST override this to provide the initial task description
        given to the LLM.

        Args:
            state: Current LangGraph state dict.

        Returns:
            Task prompt string.
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} must implement context_prompt()"
        )

    async def _run_skill(self, state: GraphState) -> Dict[str, Any]:
        """Run the generic agentic tool-calling loop.

        Builds the prompt, calls generate_with_tools(), and returns the
        raw result dict. Subclasses call this from their own ``run()``
        method and then wrap the result in the appropriate state keys.

        Args:
            state: Current LangGraph state dict.

        Returns:
            Raw result dict from the LLM (agent decision + fields).
        """
        prompt = self.context_prompt(state)
        return await self.llm.generate_with_tools(
            prompt=prompt,
            tools=self.tools,
            tool_schemas=self.tool_schemas,
            system_prompt=self.instructions,
            output_schema=self.output_schema,
        )

    def handle_agent_error(
        self,
        agent_name: str,
        exc: Exception,
        result_key: str,
        step_name: str
    ) -> Dict[str, Any]:
        """Standardized error handling for agents.

        Creates a consistent error response structure for all agents,
        reducing code duplication across agent implementations.

        Args:
            agent_name: Human-readable name of the agent for logging.
            exc: The exception that was raised.
            result_key: The state key to store the error result (e.g., "agent_1_result").
            step_name: The step name for history tracking (e.g., "completeness_agent").

        Returns:
            State update dict with error information, ready to return from run().
        """
        logger.error(f"[{agent_name}] Failed", error=str(exc))

        return {
            result_key: {
                "valid": False,
                "issues": [{"severity": "critical", "message": f"Agent error: {exc}", "field": "agent"}],
                "error": str(exc),
            },
            "current_step": f"{step_name}_error",
            "history": [{"step": step_name, "error": str(exc)}],
            "error": str(exc),
        }
