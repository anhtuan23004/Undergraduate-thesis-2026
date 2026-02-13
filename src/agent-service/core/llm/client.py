"""LLM client for generating responses."""
import json
from typing import Any, Dict, Optional

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langfuse.decorators import observe

from app.config import settings


class LLMClient:
    """Client for LLM interactions."""

    def __init__(self):
        """Initialize LLM client."""
        self.llm = ChatOpenAI(
            model=settings.OPENAI_MODEL,
            temperature=settings.OPENAI_TEMPERATURE,
            max_tokens=settings.OPENAI_MAX_TOKENS,
            api_key=settings.OPENAI_API_KEY
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

    def _capture_usage_metadata(
        self,
        response: Any,
        temperature: Optional[float] = None,
        output_type: str = "text"
    ) -> None:
        """Capture metadata for Langfuse tracing."""
        if not hasattr(response, 'usage_metadata') or not response.usage_metadata:
            return

        observe(
            model=settings.OPENAI_MODEL,
            usage={
                "input": response.usage_metadata.get("input_tokens", 0),
                "output": response.usage_metadata.get("output_tokens", 0),
            },
            metadata={
                "temperature": temperature if temperature is not None else settings.OPENAI_TEMPERATURE,
                "max_tokens": settings.OPENAI_MAX_TOKENS,
                "output_type": output_type,
            }
        )

    @observe(as_type="generation")
    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None
    ) -> str:
        """Generate text response.

        Args:
            prompt: User prompt
            system_prompt: Optional system prompt
            temperature: Optional temperature override

        Returns:
            Generated text
        """
        messages = self._build_messages(prompt, system_prompt)
        llm = self.llm.with_config(temperature=temperature) if temperature is not None else self.llm

        response = await llm.ainvoke(messages)
        self._capture_usage_metadata(response, temperature, "text")

        return response.content

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

    @observe(as_type="generation")
    async def generate_json(
        self,
        prompt: str,
        schema: Dict[str, Any],
        system_prompt: Optional[str] = None
    ) -> Dict[str, Any]:
        """Generate JSON response.

        Args:
            prompt: User prompt
            schema: JSON schema for response
            system_prompt: Optional system prompt

        Returns:
            Parsed JSON response
        """
        full_prompt = f"""{prompt}

You must respond with valid JSON matching this schema:
{json.dumps(schema, indent=2)}

Response (JSON only, no markdown):
"""

        messages = self._build_messages(full_prompt, system_prompt)
        response = await self.llm.ainvoke(messages)
        content = self._clean_json_content(response.content)

        self._capture_usage_metadata(response, output_type="json")

        try:
            return json.loads(content)
        except json.JSONDecodeError as e:
            extracted = self._extract_json_from_text(content)
            if extracted:
                return extracted

            return {
                "error": f"Failed to parse JSON: {e}",
                "raw_response": content[:500]
            }
