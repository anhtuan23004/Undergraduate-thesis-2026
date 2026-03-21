"""LLM client for LangGraph with async support and Langfuse tracing."""

import structlog
from typing import Optional
from langchain.agents import create_agent
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.tools import BaseTool as LangChainBaseTool
from langchain_core.callbacks import BaseCallbackHandler

from config import settings

logger = structlog.get_logger()


class LangfuseCallbackHandler(BaseCallbackHandler):
    """Custom Langfuse callback handler for tracing."""

    def __init__(self, trace_name: str):
        self.trace_name = trace_name
        self._handler = None

    async def setup(self):
        """Setup Langfuse handler lazily."""
        if self._handler is None and settings.LANGFUSE_ENABLED:
            try:
                from langfuse import Langfuse

                langfuse = Langfuse(
                    public_key=settings.LANGFUSE_PUBLIC_KEY,
                    secret_key=settings.LANGFUSE_SECRET_KEY,
                    host=settings.LANGFUSE_HOST,
                )
                self._handler = langfuse.new_callback(
                    trace_name=self.trace_name,
                    metadata={"service": "agent-service"},
                )
            except Exception as e:
                logger.warning("Failed to initialize Langfuse", error=str(e))
                self._handler = None

    @property
    def handler(self) -> Optional[BaseCallbackHandler]:
        return self._handler

    async def on_agent_action(self, action, *args, **kwargs):
        if self._handler and hasattr(self._handler, "on_agent_action"):
            await self._handler.on_agent_action(action, *args, **kwargs)

    async def on_tool_start(self, serialized, input_str, *args, **kwargs):
        if self._handler and hasattr(self._handler, "on_tool_start"):
            await self._handler.on_tool_start(serialized, input_str, *args, **kwargs)

    async def on_tool_end(self, output, *args, **kwargs):
        if self._handler and hasattr(self._handler, "on_tool_end"):
            await self._handler.on_tool_end(output, *args, **kwargs)


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
        trace_name: str = "agent_invocation",
        metadata: Optional[dict] = None,
    ) -> dict:
        """Invoke agent asynchronously without blocking event loop."""
        langfuse_callback = LangfuseCallbackHandler(trace_name)
        await langfuse_callback.setup()

        callbacks = []
        if langfuse_callback.handler:
            callbacks.append(langfuse_callback.handler)

        agent = create_agent(
            self._llm,
            tools=tools,
            state_modifier=system_prompt,
        )

        try:
            result = await agent.ainvoke(
                {"messages": [{"role": "user", "content": prompt}]},
                config={"callbacks": callbacks} if callbacks else {},
            )
            return result
        except Exception as e:
            logger.error("Agent invocation failed", error=str(e))
            return {
                "messages": [{"role": "assistant", "content": f"Error: {e}"}],
                "error": str(e),
            }


_client_instance = None


def get_llm_client() -> LangGraphLLMClient:
    """Get or create singleton LLM client."""
    global _client_instance
    if _client_instance is None:
        _client_instance = LangGraphLLMClient()
    return _client_instance
