"""LLM client for generating responses."""
import json
import inspect
import asyncio
import random
import structlog
from typing import Any, Dict, List, Optional, TYPE_CHECKING

logger = structlog.get_logger()


def _should_retry_exception(exc: Exception) -> bool:
    """Check if an exception is retryable (rate limit, timeout, etc.)."""
    retryable_errors = (
        "rate limit",
        "rate_limit",
        "429",
        "timeout",
        "connection",
        "temporarily unavailable",
        "503",
        "500",
        "internal server error",
    )
    exc_str = str(exc).lower()
    return any(err in exc_str for err in retryable_errors)


async def _async_retry(
    func,
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    **kwargs
) -> Any:
    """Execute an async function with exponential backoff retry logic.

    Args:
        func: Async function to execute.
        max_retries: Maximum number of retry attempts.
        base_delay: Initial delay between retries (seconds).
        max_delay: Maximum delay between retries (seconds).
        **kwargs: Arguments to pass to func.

    Returns:
        Result from func.

    Raises:
        Exception: The last exception if all retries fail.
    """
    last_exception = None
    for attempt in range(max_retries):
        try:
            return await func(**kwargs)
        except Exception as exc:
            last_exception = exc
            if attempt < max_retries - 1 and _should_retry_exception(exc):
                delay = min(base_delay * (2 ** attempt), max_delay)
                # Add jitter (0-25% of delay) to avoid thundering herd
                jitter = delay * 0.25 * random.random()
                delay = delay + jitter
                logger.warning(
                    "LLM call failed, retrying",
                    attempt=attempt + 1,
                    max_retries=max_retries,
                    delay=round(delay, 2),
                    error=str(exc)
                )
                await asyncio.sleep(delay)
            else:
                break
    raise last_exception

if TYPE_CHECKING:
    from core.base.tool import BaseTool


from langchain_core.messages import HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI

from config import settings


class LLMClient:
    """Client for LLM interactions."""

    def __init__(self):
        """Initialize LLM client."""
        self.llm = ChatGoogleGenerativeAI(
            model=settings.GEMINI_MODEL,
            temperature=settings.GEMINI_TEMPERATURE,
            max_tokens=settings.GEMINI_MAX_TOKENS,
            api_key=settings.GEMINI_API_KEY
        )

    def _build_messages(
        self,
        prompt: str,
        system_prompt: Optional[str] = None
    ) -> list:
        """Build message list for LLM invocation."""
        messages = []
        if system_prompt:
            messages.append(SystemMessage(content=system_prompt))
        messages.append(HumanMessage(content=prompt))
        return messages

    async def _generate_impl(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None
    ) -> str:
        """Implementation of generate without retry logic."""
        messages = self._build_messages(prompt, system_prompt)
        llm = self.llm.with_config(temperature=temperature) if temperature is not None else self.llm

        response = await llm.ainvoke(messages)

        return self._extract_text_content(response.content)

    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None
    ) -> str:
        """Generate text response with retry logic.

        Args:
            prompt: User prompt
            system_prompt: Optional system prompt
            temperature: Optional temperature override

        Returns:
            Generated text
        """
        return await _async_retry(
            self._generate_impl,
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=temperature
        )

    @staticmethod
    def _extract_text_content(content: Any) -> str:
        """Safely extract string text from a Gemini response content.

        Gemini returns content as a plain string in text mode, but as a
        list of content blocks (some text, some tool_call) in tool-calling
        mode. This helper normalises both forms to a plain string.

        Args:
            content: The response.content value from an AIMessage.

        Returns:
            Concatenated text from all text blocks, or empty string.
        """
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts = []
            for block in content:
                if isinstance(block, str):
                    parts.append(block)
                elif isinstance(block, dict):
                    parts.append(block.get("text", ""))
                elif hasattr(block, "text"):
                    parts.append(block.text or "")
            return " ".join(p for p in parts if p).strip()
        return str(content)

    @staticmethod
    def _clean_json_content(content: str) -> str:
        """Clean markdown formatting from JSON content."""
        content = content.strip()
        for prefix in ["```json", "```"]:
            if content.startswith(prefix):
                content = content[len(prefix):]
        if content.endswith("```"):
            content = content[:-3]
        return content.strip()

    @staticmethod
    def _extract_json_from_text(content: str) -> Optional[Dict[str, Any]]:
        """Try to extract JSON from text response."""
        start = content.find("{")
        end = content.rfind("}") + 1
        if start >= 0 and end > start:
            return json.loads(content[start:end])
        return None

    async def _generate_json_impl(
        self,
        prompt: str,
        schema: Dict[str, Any],
        system_prompt: Optional[str] = None
    ) -> Dict[str, Any]:
        """Implementation of generate_json without retry logic."""
        full_prompt = f"""{prompt}

You must respond with valid JSON matching this schema:
{json.dumps(schema, indent=2)}

Response (JSON only, no markdown):
"""

        messages = self._build_messages(full_prompt, system_prompt)
        response = await self.llm.ainvoke(messages)
        content = self._clean_json_content(self._extract_text_content(response.content))

        try:
            return json.loads(content)
        except json.JSONDecodeError as e:
            extracted = self._extract_json_from_text(content)
            if extracted:
                return extracted

            return {
                "error": f"Failed to parse JSON: {e}",
                "raw_response": content
            }

    async def generate_json(
        self,
        prompt: str,
        schema: Dict[str, Any],
        system_prompt: Optional[str] = None
    ) -> Dict[str, Any]:
        """Generate JSON response with retry logic.

        Args:
            prompt: User prompt
            schema: JSON schema for response
            system_prompt: Optional system prompt

        Returns:
            Parsed JSON response
        """
        return await _async_retry(
            self._generate_json_impl,
            prompt=prompt,
            schema=schema,
            system_prompt=system_prompt
        )

    async def generate_with_tools(
        self,
        prompt: str,
        tools: List[Any],
        tool_schemas: List[Dict[str, Any]],
        system_prompt: str,
        output_schema: Dict[str, Any],
        max_iterations: int = 6,
    ) -> Dict[str, Any]:
        """Run an agentic tool-calling loop using Gemini function-calling.

        The LLM is given tool schemas (from config/schemas/*.json) as Gemini
        function definitions. It iteratively:
          1. Picks a tool call (or produces final JSON if done)
          2. Agent executes the tool
          3. Tool result is fed back as context
          4. Loop repeats until no more tool calls (max_iterations safety)

        Falls back to prompt-injection if bind_tools / function-calling fails.

        Args:
            prompt: Initial task description for the LLM.
            tools: List of tool instances (with async execute() method).
            tool_schemas: List of JSON schemas from config/schemas/*.json.
            system_prompt: Skill instructions from config/instructions/*.md.
            output_schema: Expected output schema (from agents/*.yaml).
            max_iterations: Maximum tool-call iterations before forcing output.

        Returns:
            Parsed final JSON from the LLM containing the agent decision.
        """
        # Build tool name → instance map for dispatch
        tool_map: Dict[str, Any] = {t.name: t for t in tools}

        try:
            from langchain_core.tools import StructuredTool
            from langchain_core.messages import ToolMessage, AIMessage
            from pydantic import BaseModel, Field, create_model
            from typing import Optional as Opt, Literal
            import typing

            def _build_pydantic_model(schema: Dict[str, Any]) -> type:
                """Build a Pydantic model from a JSON parameters schema."""
                properties = schema.get("parameters", {}).get("properties", {})
                required = schema.get("parameters", {}).get("required", [])
                fields: Dict[str, Any] = {}
                for field_name, field_def in properties.items():
                    desc = field_def.get("description", "")
                    ftype = field_def.get("type", "string")
                    enum_vals = field_def.get("enum")
                    if enum_vals:
                        # Use Literal for enum fields so Gemini sees the constraints
                        literal = Literal[tuple(enum_vals)]  # type: ignore[misc]
                        if field_name in required:
                            fields[field_name] = (literal, Field(description=desc))
                        else:
                            fields[field_name] = (Opt[literal], Field(default=None, description=desc))  # type: ignore[valid-type]
                    elif ftype == "integer":
                        ann = int if field_name in required else Opt[int]
                        fields[field_name] = (ann, Field(default=None if field_name not in required else ..., description=desc))
                    elif ftype == "number":
                        ann = float if field_name in required else Opt[float]
                        fields[field_name] = (ann, Field(default=None if field_name not in required else ..., description=desc))
                    elif ftype == "array":
                        ann = Opt[list]
                        fields[field_name] = (ann, Field(default=None, description=desc))
                    else:
                        ann = str if field_name in required else Opt[str]
                        fields[field_name] = (ann, Field(default=None if field_name not in required else ..., description=desc))

                model_name = schema.get("name", "Tool").replace("_", " ").title().replace(" ", "") + "Args"
                return create_model(model_name, **fields)

            lc_tools = []
            for schema in tool_schemas:
                tool_name = schema.get("name", "")
                if not tool_map.get(tool_name):
                    continue

                def _make_noop(name: str):
                    def _noop(**kwargs):
                        return f"__pending__{name}"
                    _noop.__name__ = name
                    return _noop

                try:
                    args_model = _build_pydantic_model(schema)
                except Exception:
                    args_model = None

                lc_tool = StructuredTool.from_function(
                    func=_make_noop(tool_name),
                    name=tool_name,
                    description=schema.get("description", ""),
                    args_schema=args_model,
                )
                lc_tools.append(lc_tool)

            llm_with_tools = self.llm.bind_tools(lc_tools)

            messages = []
            if system_prompt:
                messages.append(SystemMessage(content=system_prompt))
            messages.append(HumanMessage(content=prompt))

            for iteration in range(max_iterations):
                response: AIMessage = await llm_with_tools.ainvoke(messages)
                messages.append(response)

                tool_calls = getattr(response, "tool_calls", []) or []
                if not tool_calls:
                    # Try to extract JSON from whatever text LLM returned
                    raw_text = self._extract_text_content(response.content)
                    content = self._clean_json_content(raw_text)
                    try:
                        return json.loads(content)
                    except json.JSONDecodeError:
                        extracted = self._extract_json_from_text(content)
                        if extracted:
                            return extracted

                    # Content was empty or non-JSON — LLM finished tool calls.
                    # Build a clean 2-message conversation for the final JSON request.
                    # We CANNOT pass ToolMessage history to plain llm.ainvoke — Gemini
                    # returns empty when that happens. Instead, flatten tool results into text.
                    tool_results_summary = []
                    for msg in messages:
                        if hasattr(msg, "tool_call_id"):  # ToolMessage
                            tool_results_summary.append(f"Tool result: {msg.content}")
                    summary_prompt = (
                        f"{prompt}\n\n"
                        f"Tool results collected:\n" + "\n".join(tool_results_summary) + "\n\n"
                        f"Based on these results, provide your final decision as valid JSON "
                        f"matching this schema:\n{json.dumps(output_schema, indent=2)}\n"
                        f"JSON only, no markdown:"
                    )
                    clean_messages = []
                    if system_prompt:
                        clean_messages.append(SystemMessage(content=system_prompt))
                    clean_messages.append(HumanMessage(content=summary_prompt))
                    final_resp = await self.llm.ainvoke(clean_messages)
                    final_text = self._clean_json_content(self._extract_text_content(final_resp.content))
                    try:
                        return json.loads(final_text)
                    except json.JSONDecodeError:
                        result = self._extract_json_from_text(final_text)
                        if result:
                            return result
                    # Still no JSON — continue loop
                    continue

                # Execute each tool call and feed results back
                for tc in tool_calls:
                    tool_name = tc.get("name", "")
                    tool_args = tc.get("args", {})
                    tool_call_id = tc.get("id", tool_name)

                    tool_inst = tool_map.get(tool_name)
                    if tool_inst:
                        try:
                            if inspect.iscoroutinefunction(tool_inst.execute):
                                result = await tool_inst.execute(**tool_args)
                            else:
                                result = tool_inst.execute(**tool_args)
                        except Exception as exc:
                            result = {"error": str(exc), "tool": tool_name}
                    else:
                        result = {"error": f"Tool '{tool_name}' not found"}

                    messages.append(ToolMessage(
                        content=json.dumps(result),
                        tool_call_id=tool_call_id,
                    ))

            # Exhausted iterations — force final JSON output
            messages.append(HumanMessage(
                content=(
                    f"Provide your final answer as valid JSON matching:\n"
                    f"{json.dumps(output_schema, indent=2)}\nJSON only:"
                )
            ))
            final = await self.llm.ainvoke(messages)
            content = self._clean_json_content(
                self._extract_text_content(final.content)
            )
            try:
                return json.loads(content)
            except json.JSONDecodeError:
                return self._extract_json_from_text(content) or {
                    "error": "Max iterations reached without valid JSON",
                    "raw": content[:500]
                }

        except Exception as exc:
            # WHY: We cannot call tool.execute() here with no args — tools require
            # mandatory parameters (e.g. file_path) that we don't have in this scope.
            # Fall back directly to a plain generate_json call using the original prompt,
            # which is the safest option when bind_tools / function-calling fails entirely.
            logger.error(
                "generate_with_tools: bind_tools failed, falling back to generate_json",
                error=str(exc)
            )
            return await self.generate_json(
                prompt=prompt,
                schema=output_schema,
                system_prompt=system_prompt,
            )

