"""LLM client for generating responses."""
import json
from typing import Optional, Dict, Any

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
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
        messages = []

        if system_prompt:
            messages.append(SystemMessage(content=system_prompt))

        messages.append(HumanMessage(content=prompt))

        # Override temperature if provided
        if temperature is not None:
            llm = self.llm.with_config(temperature=temperature)
        else:
            llm = self.llm

        response = await llm.ainvoke(messages)

        # Capture metadata for Langfuse tracing
        if hasattr(response, 'usage_metadata') and response.usage_metadata:
            observe(
                model=settings.OPENAI_MODEL,
                usage={
                    "input": response.usage_metadata.get("input_tokens", 0),
                    "output": response.usage_metadata.get("output_tokens", 0),
                },
                metadata={
                    "temperature": temperature if temperature is not None else settings.OPENAI_TEMPERATURE,
                    "max_tokens": settings.OPENAI_MAX_TOKENS,
                }
            )

        return response.content

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
        # Add schema to prompt
        full_prompt = f"""{prompt}

You must respond with valid JSON matching this schema:
{json.dumps(schema, indent=2)}

Response (JSON only, no markdown):
"""

        messages = []

        if system_prompt:
            messages.append(SystemMessage(content=system_prompt))

        messages.append(HumanMessage(content=full_prompt))

        response = await self.llm.ainvoke(messages)
        content = response.content

        # Capture metadata for Langfuse tracing
        if hasattr(response, 'usage_metadata') and response.usage_metadata:
            observe(
                model=settings.OPENAI_MODEL,
                usage={
                    "input": response.usage_metadata.get("input_tokens", 0),
                    "output": response.usage_metadata.get("output_tokens", 0),
                },
                metadata={
                    "temperature": settings.OPENAI_TEMPERATURE,
                    "max_tokens": settings.OPENAI_MAX_TOKENS,
                    "output_type": "json",
                }
            )

        # Clean up markdown if present
        if content.startswith("```json"):
            content = content[7:]
        if content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]

        content = content.strip()

        try:
            return json.loads(content)
        except json.JSONDecodeError as e:
            # Try to extract JSON from text
            try:
                start = content.find("{")
                end = content.rfind("}") + 1
                if start >= 0 and end > start:
                    return json.loads(content[start:end])
            except:
                pass

            # Return error structure
            return {
                "error": f"Failed to parse JSON: {e}",
                "raw_response": content[:500]
            }
