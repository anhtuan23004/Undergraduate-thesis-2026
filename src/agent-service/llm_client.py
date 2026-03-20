"""LLM client for LangGraph with async support."""

import asyncio
import structlog
from langchain.agents import create_agent
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.tools import BaseTool as LangChainBaseTool

from config import settings

logger = structlog.get_logger()


class LangGraphLLMClient:
    """LLM client with proper async handling for LangGraph workflows."""

    def __init__(self):
        self._llm = ChatGoogleGenerativeAI(
            model=settings.GEMINI_MODEL,
            google_api_key=settings.GEMINI_API_KEY,
            temperature=settings.GEMINI_TEMPERATURE,
            max_output_tokens=settings.GEMINI_MAX_TOKENS,
        )
        logger.info("LLM Client initialized", model=settings.GEMINI_MODEL)

    async def invoke_agent(
        self,
        prompt: str,
        tools: list[LangChainBaseTool],
        system_prompt: str,
    ) -> dict:
        """Invoke agent asynchronously without blocking event loop."""
        agent = create_agent(
            self._llm,
            tools=tools,
            system_prompt=system_prompt,
        )

        try:
            result = await agent.ainvoke(
                {"messages": [{"role": "user", "content": prompt}]}
            )
            return result
        except Exception as e:
            logger.error("Agent invocation failed", error=str(e))
            return {
                "messages": [{"role": "assistant", "content": f"Error: {str(e)}"}],
                "error": str(e),
            }


_client_instance = None


def get_llm_client() -> LangGraphLLMClient:
    """Get or create singleton LLM client."""
    global _client_instance
    if _client_instance is None:
        _client_instance = LangGraphLLMClient()
    return _client_instance
