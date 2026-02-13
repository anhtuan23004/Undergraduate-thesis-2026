"""Skill executor - loads SKILL.md and manages sub-agent execution.

The executor:
1. Loads SKILL.md content and instructions
2. Injects into sub-agent LLM context
3. Handles tool calling loops
4. Manages execution state
"""
import json
from typing import Any, Dict, List, Optional

import structlog
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from core.llm.client import LLMClient
from core.orchestrator.models import ExecutionContext, ExecutionResult, ToolResult
from core.orchestrator.tools import ToolRegistry

logger = structlog.get_logger()


class SkillExecutor:
    """Executes skills with tool calling capabilities.

    The executor runs a sub-agent loop:
    1. Load skill instructions
    2. Set up tool registry with allowed tools
    3. Run LLM with tools
    4. Execute tool calls
    5. Continue until completion or max iterations
    """

    def __init__(
        self,
        llm_client: Optional[LLMClient] = None,
        max_iterations: int = 10
    ):
        """Initialize the executor.

        Args:
            llm_client: LLM client for sub-agent
            max_iterations: Maximum tool calling iterations
        """
        self.llm = llm_client or LLMClient()
        self.max_iterations = max_iterations
        self.logger = logger.bind(component="skill_executor")

    async def execute(self, context: ExecutionContext) -> ExecutionResult:
        """Execute a skill with tool calling.

        Args:
            context: Execution context with skill and user input

        Returns:
            Execution result
        """
        import time
        start_time = time.time()

        self.logger.info(
            "Starting skill execution",
            skill=context.skill.name,
            tools_allowed=context.skill.tools_allowed
        )

        # Set up tool registry
        tool_registry = ToolRegistry(
            allowed_tools=context.skill.tools_allowed or None
        )

        # Build initial messages
        messages = self._build_messages(context)

        tool_calls_count = 0

        try:
            for iteration in range(self.max_iterations):
                self.logger.debug(
                    "LLM iteration",
                    iteration=iteration + 1,
                    max_iterations=self.max_iterations
                )

                # Get LLM response with tools
                response = await self._call_llm_with_tools(
                    messages,
                    tool_registry
                )

                # Add assistant message
                messages.append(AIMessage(content=response.get("content", "")))

                # Check for tool calls
                tool_calls = response.get("tool_calls", [])

                if not tool_calls:
                    # No tool calls - execution complete
                    execution_time = (time.time() - start_time) * 1000

                    self.logger.info(
                        "Skill execution complete",
                        skill=context.skill.name,
                        tool_calls=tool_calls_count,
                        execution_time_ms=execution_time
                    )

                    return ExecutionResult(
                        success=True,
                        output=response.get("content", ""),
                        tool_calls_count=tool_calls_count,
                        execution_time_ms=execution_time
                    )

                # Execute tool calls
                for tool_call in tool_calls:
                    tool_calls_count += 1
                    tool_name = tool_call.get("name")
                    tool_params = tool_call.get("parameters", {})

                    self.logger.debug(
                        "Executing tool",
                        tool=tool_name,
                        params=list(tool_params.keys())
                    )

                    # Execute tool
                    tool = tool_registry.get_tool(tool_name)
                    if tool:
                        result = await tool(**tool_params)
                    else:
                        result = ToolResult(
                            success=False,
                            error=f"Tool '{tool_name}' not allowed or not found"
                        )

                    # Record tool call
                    context.add_tool_call(tool_name, tool_params, result)

                    # Add tool result to messages
                    tool_result_content = self._format_tool_result(result)
                    messages.append(ToolMessage(
                        content=tool_result_content,
                        tool_call_id=tool_call.get("id", f"call_{tool_calls_count}")
                    ))

            # Max iterations reached
            execution_time = (time.time() - start_time) * 1000
            return ExecutionResult(
                success=False,
                error=f"Max iterations ({self.max_iterations}) reached",
                output=messages[-1].content if messages else "",
                tool_calls_count=tool_calls_count,
                execution_time_ms=execution_time
            )

        except Exception as e:
            execution_time = (time.time() - start_time) * 1000
            self.logger.error(
                "Skill execution failed",
                skill=context.skill.name,
                error=str(e)
            )

            return ExecutionResult(
                success=False,
                error=str(e),
                tool_calls_count=tool_calls_count,
                execution_time_ms=execution_time
            )

    def _build_messages(self, context: ExecutionContext) -> List:
        """Build initial message list for LLM.

        Args:
            context: Execution context

        Returns:
            List of LangChain messages
        """
        messages = []

        # System message with skill instructions
        system_prompt = self._build_system_prompt(context)
        messages.append(SystemMessage(content=system_prompt))

        # Conversation history
        for msg in context.conversation_history:
            role = msg.get("role")
            content = msg.get("content", "")
            if role == "user":
                messages.append(HumanMessage(content=content))
            elif role == "assistant":
                messages.append(AIMessage(content=content))

        # Current user input
        messages.append(HumanMessage(content=context.user_input))

        return messages

    def _build_system_prompt(self, context: ExecutionContext) -> str:
        """Build system prompt with skill instructions.

        Args:
            context: Execution context

        Returns:
            System prompt string
        """
        skill = context.skill

        prompt = f"""You are executing the '{skill.name}' skill.

## Description
{skill.description}

## Instructions
{skill.instructions}

## Available Tools
You have access to the following tools:
"""

        # Add tool descriptions
        tool_registry = ToolRegistry(allowed_tools=skill.tools_allowed)
        for tool_name in tool_registry.list_tools():
            schemas = tool_registry.get_tool_schemas()
            if tool_name in schemas:
                schema = schemas[tool_name]
                prompt += f"\n### {schema['name']}\n"
                prompt += f"{schema['description']}\n"

        prompt += """
## How to Use Tools

When you need to use a tool, respond with a tool call in this format:
```tool
{
  "name": "tool_name",
  "parameters": {
    "param1": "value1",
    "param2": "value2"
  }
}
```

The system will execute the tool and return the result. You can then continue
with additional tool calls or provide your final response.

## Working Directory
"""
        prompt += f"{context.working_directory or Path.cwd()}"

        return prompt

    async def _call_llm_with_tools(
        self,
        messages: List,
        tool_registry: ToolRegistry
    ) -> Dict[str, Any]:
        """Call LLM with tool definitions.

        Args:
            messages: Message history
            tool_registry: Tool registry with available tools

        Returns:
            Response with content and tool_calls
        """
        # Get tool schemas for function calling
        tools = tool_registry.get_tool_schemas()

        # Build prompt with tool instructions
        system_prompt = None
        user_messages = []

        for msg in messages:
            if isinstance(msg, SystemMessage):
                system_prompt = msg.content
            elif isinstance(msg, HumanMessage):
                user_messages.append(msg.content)
            elif isinstance(msg, AIMessage):
                user_messages.append(f"Assistant: {msg.content}")
            elif isinstance(msg, ToolMessage):
                user_messages.append(f"Tool result: {msg.content}")

        full_prompt = "\n\n".join(user_messages)

        # Add tool instructions
        tool_instructions = """
\n\nYou can use tools by including TOOL_CALL blocks in your response.
Format: TOOL_CALL {"name": "tool_name", "parameters": {...}}

If you don't need tools, respond normally.
"""
        full_prompt += tool_instructions

        # Generate response
        response_text = await self.llm.generate(
            prompt=full_prompt,
            system_prompt=system_prompt
        )

        # Parse tool calls from response
        tool_calls = self._parse_tool_calls(response_text)

        # Remove tool calls from content for cleaner output
        content = self._remove_tool_calls(response_text)

        return {
            "content": content,
            "tool_calls": tool_calls,
            "raw_response": response_text
        }

    def _parse_tool_calls(self, text: str) -> List[Dict[str, Any]]:
        """Parse tool calls from LLM response.

        Args:
            text: LLM response text

        Returns:
            List of tool call dictionaries
        """
        import re

        tool_calls = []

        # Match TOOL_CALL {...} pattern
        pattern = r'TOOL_CALL\s*(\{[^}]+\})'
        matches = re.findall(pattern, text, re.DOTALL)

        for i, match in enumerate(matches):
            try:
                # Try to parse as JSON
                tool_call = json.loads(match)
                tool_call["id"] = f"call_{i}"
                tool_calls.append(tool_call)
            except json.JSONDecodeError:
                self.logger.warning("Failed to parse tool call", match=match[:100])

        return tool_calls

    def _remove_tool_calls(self, text: str) -> str:
        """Remove tool calls from response text.

        Args:
            text: Original response

        Returns:
            Cleaned response
        """
        import re
        # Remove TOOL_CALL blocks
        cleaned = re.sub(r'TOOL_CALL\s*\{[^}]+\}', '', text, flags=re.DOTALL)
        return cleaned.strip()

    def _format_tool_result(self, result: ToolResult) -> str:
        """Format tool result for LLM consumption.

        Args:
            result: Tool execution result

        Returns:
            Formatted string
        """
        if result.success:
            output = result.output
            if result.metadata:
                output += f"\n\n[Metadata: {json.dumps(result.metadata)}]"
            return output
        else:
            error = result.error or "Unknown error"
            return f"[Error: {error}]"
