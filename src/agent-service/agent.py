"""LLM client for LangGraph with async support and Langfuse tracing."""

import structlog
import os
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
            if settings.LANGFUSE_PUBLIC_KEY:
                os.environ.setdefault("LANGFUSE_PUBLIC_KEY", settings.LANGFUSE_PUBLIC_KEY)
            if settings.LANGFUSE_SECRET_KEY:
                os.environ.setdefault("LANGFUSE_SECRET_KEY", settings.LANGFUSE_SECRET_KEY)
            if settings.LANGFUSE_HOST:
                os.environ.setdefault("LANGFUSE_HOST", settings.LANGFUSE_HOST)

            try:
                from langfuse import Langfuse
                from langfuse.langchain import CallbackHandler

                langfuse_client = Langfuse(
                    public_key=settings.LANGFUSE_PUBLIC_KEY,
                    secret_key=settings.LANGFUSE_SECRET_KEY,
                    host=settings.LANGFUSE_HOST,
                )
                try:
                    self._handler = CallbackHandler(langfuse=langfuse_client)
                except TypeError:
                    self._handler = CallbackHandler()

                logger.info("Langfuse callback handler initialized", trace_name=self.trace_name)
            except ImportError:
                logger.warning("Langfuse is enabled but package is not installed.")
            except Exception as exc:
                logger.warning("Langfuse callback disabled due to init error", error=str(exc))

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
            model=self._llm,
            tools=tools,
            system_prompt=system_prompt,
        )

        try:
            config = {"run_name": trace_name}
            if callbacks:
                config["callbacks"] = callbacks

            result = await agent.ainvoke(
                {"messages": [{"role": "user", "content": prompt}]},
                config=config,
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
