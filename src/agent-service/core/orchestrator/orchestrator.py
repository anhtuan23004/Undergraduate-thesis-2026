"""Agent Orchestrator using LangGraph for coordination.

The orchestrator manages the flow:
1. Route - Determine which skill to use
2. Execute - Run the skill with tool calling
3. Complete - Return final result

Uses LangGraph for state management and execution flow.
"""
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Annotated, Any, Dict, List, Optional, TypedDict

import structlog
from langgraph.graph import END, StateGraph
from langgraph.graph.message import add_messages

from core.llm.client import LLMClient
from core.orchestrator.discovery import SkillDiscovery
from core.orchestrator.executor import SkillExecutor
from core.orchestrator.models import ExecutionContext, ExecutionResult, SkillInfo

logger = structlog.get_logger()


class OrchestratorState(TypedDict):
    """State for the orchestrator graph."""
    messages: Annotated[list, add_messages]
    user_input: str
    selected_skill: Optional[str]
    skill_result: Optional[Dict[str, Any]]
    error: Optional[str]
    complete: bool


@dataclass
class OrchestratorConfig:
    """Configuration for the orchestrator."""
    skills_dir: str = "./skills"
    max_iterations: int = 10
    default_skill: Optional[str] = None
    routing_prompt: str = field(default_factory=lambda: """You are an orchestrator that routes user requests to the appropriate skill.

Available skills:
{skills}

User request: {user_input}

Analyze the request and select the most appropriate skill. Respond with ONLY the skill name.
If no skill matches, respond with "none".
""")


class AgentOrchestrator:
    """Main orchestrator for skill-based agent execution.

    Usage:
        orchestrator = AgentOrchestrator()

        # Simple usage
        result = await orchestrator.process("Search for Python tutorials")

        # With specific skill
        result = await orchestrator.process(
            "Search for Python tutorials",
            skill_name="web_search"
        )
    """

    def __init__(
        self,
        config: Optional[OrchestratorConfig] = None,
        llm_client: Optional[LLMClient] = None
    ):
        """Initialize the orchestrator.

        Args:
            config: Orchestrator configuration
            llm_client: LLM client for routing and execution
        """
        self.config = config or OrchestratorConfig()
        self.llm = llm_client or LLMClient()
        self.logger = logger.bind(component="orchestrator")

        # Initialize components
        self.discovery = SkillDiscovery(self.config.skills_dir)
        self.executor = SkillExecutor(
            llm_client=self.llm,
            max_iterations=self.config.max_iterations
        )

        # Build the graph
        self.graph = self._build_graph()

        # Cache discovered skills
        self._skills: Dict[str, SkillInfo] = {}

    async def discover_skills(self) -> List[SkillInfo]:
        """Discover all available skills.

        Returns:
            List of discovered skills
        """
        skills = self.discovery.discover_all()
        self._skills = {s.name: s for s in skills}
        return skills

    async def process(
        self,
        user_input: str,
        skill_name: Optional[str] = None,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        working_directory: Optional[str] = None
    ) -> ExecutionResult:
        """Process a user request.

        Args:
            user_input: User's request text
            skill_name: Optional specific skill to use
            conversation_history: Previous conversation messages
            working_directory: Working directory for execution

        Returns:
            Execution result
        """
        # Ensure skills are discovered
        if not self._skills:
            await self.discover_skills()

        # If skill_name provided, use it directly
        if skill_name:
            return await self._execute_skill(
                skill_name=skill_name,
                user_input=user_input,
                conversation_history=conversation_history or [],
                working_directory=working_directory
            )

        # Otherwise, use the graph for routing
        initial_state: OrchestratorState = {
            "messages": [{"role": "user", "content": user_input}],
            "user_input": user_input,
            "selected_skill": None,
            "skill_result": None,
            "error": None,
            "complete": False
        }

        # Run the graph
        result = await self.graph.ainvoke(initial_state)

        # Extract result
        if result.get("error"):
            return ExecutionResult(
                success=False,
                error=result["error"]
            )

        skill_result = result.get("skill_result", {})
        return ExecutionResult(
            success=skill_result.get("success", False),
            output=skill_result.get("output", ""),
            error=skill_result.get("error"),
            tool_calls_count=skill_result.get("tool_calls_count", 0),
            execution_time_ms=skill_result.get("execution_time_ms", 0)
        )

    async def _execute_skill(
        self,
        skill_name: str,
        user_input: str,
        conversation_history: List[Dict[str, str]],
        working_directory: Optional[str] = None
    ) -> ExecutionResult:
        """Execute a specific skill.

        Args:
            skill_name: Name of skill to execute
            user_input: User input
            conversation_history: Conversation history
            working_directory: Working directory

        Returns:
            Execution result
        """
        skill = self._skills.get(skill_name)
        if not skill:
            return ExecutionResult(
                success=False,
                error=f"Skill '{skill_name}' not found"
            )

        context = ExecutionContext(
            skill=skill,
            user_input=user_input,
            conversation_history=conversation_history,
            working_directory=working_directory or str(Path.cwd())
        )

        return await self.executor.execute(context)

    def _build_graph(self) -> StateGraph:
        """Build the LangGraph for orchestration.

        Returns:
            Compiled StateGraph
        """
        workflow = StateGraph(OrchestratorState)

        # Add nodes
        workflow.add_node("route", self._route_node)
        workflow.add_node("execute", self._execute_node)
        workflow.add_node("complete", self._complete_node)

        # Set entry point
        workflow.set_entry_point("route")

        # Add edges
        workflow.add_conditional_edges(
            "route",
            self._should_execute,
            {
                "execute": "execute",
                "complete": "complete"
            }
        )
        workflow.add_edge("execute", "complete")
        workflow.add_edge("complete", END)

        return workflow.compile()

    async def _route_node(self, state: OrchestratorState) -> OrchestratorState:
        """Route node - selects appropriate skill.

        Args:
            state: Current state

        Returns:
            Updated state
        """
        # If skill already selected, skip
        if state.get("selected_skill"):
            return state

        # Build skills list for routing prompt
        skills_list = "\n".join([
            f"- {name}: {skill.description}"
            for name, skill in self._skills.items()
        ])

        prompt = self.config.routing_prompt.format(
            skills=skills_list,
            user_input=state["user_input"]
        )

        try:
            response = await self.llm.generate(prompt=prompt)
            selected_skill = response.strip().lower()

            # Validate selection
            if selected_skill == "none" or selected_skill not in self._skills:
                # Try default skill
                if self.config.default_skill and self.config.default_skill in self._skills:
                    selected_skill = self.config.default_skill
                else:
                    return {
                        **state,
                        "error": f"No matching skill found for: {state['user_input']}",
                        "complete": True
                    }

            self.logger.info(
                "Routed to skill",
                skill=selected_skill,
                user_input=state["user_input"][:100]
            )

            return {
                **state,
                "selected_skill": selected_skill
            }

        except Exception as e:
            self.logger.error("Routing failed", error=str(e))
            return {
                **state,
                "error": f"Routing failed: {e}",
                "complete": True
            }

    async def _execute_node(self, state: OrchestratorState) -> OrchestratorState:
        """Execute node - runs the selected skill.

        Args:
            state: Current state

        Returns:
            Updated state
        """
        skill_name = state.get("selected_skill")
        if not skill_name:
            return {
                **state,
                "error": "No skill selected"
            }

        result = await self._execute_skill(
            skill_name=skill_name,
            user_input=state["user_input"],
            conversation_history=[]
        )

        return {
            **state,
            "skill_result": {
                "success": result.success,
                "output": result.output,
                "error": result.error,
                "tool_calls_count": result.tool_calls_count,
                "execution_time_ms": result.execution_time_ms
            }
        }

    async def _complete_node(self, state: OrchestratorState) -> OrchestratorState:
        """Complete node - finalizes execution.

        Args:
            state: Current state

        Returns:
            Updated state
        """
        return {
            **state,
            "complete": True
        }

    def _should_execute(self, state: OrchestratorState) -> str:
        """Determine if we should execute or complete.

        Args:
            state: Current state

        Returns:
            "execute" or "complete"
        """
        if state.get("error"):
            return "complete"
        if state.get("selected_skill"):
            return "execute"
        return "complete"

    def list_skills(self) -> List[SkillInfo]:
        """List all available skills.

        Returns:
            List of skill info
        """
        return list(self._skills.values())