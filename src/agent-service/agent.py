"""LLM client for LangGraph with async support and Langfuse tracing."""

import os
from typing import Any

import structlog
from config import settings
from langchain.agents import create_agent
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.tools import BaseTool as LangChainBaseTool
from langchain_google_genai import ChatGoogleGenerativeAI

logger = structlog.get_logger()
_OTEL_DETACH_PATCHED = False
_LANGFUSE_CLIENT_READY = False


def _configure_langfuse_env() -> None:
    """Expose Langfuse settings through the env names expected by the SDK."""
    env_values = {
        "LANGFUSE_PUBLIC_KEY": settings.LANGFUSE_PUBLIC_KEY,
        "LANGFUSE_SECRET_KEY": settings.LANGFUSE_SECRET_KEY,
        "LANGFUSE_HOST": settings.LANGFUSE_HOST,
    }
    for key, value in env_values.items():
        if value:
            os.environ.setdefault(key, value)


def _patch_opentelemetry_detach_for_async_langfuse() -> None:
    """Suppress expected context detach noise from Langfuse in async LangGraph runs."""
    global _OTEL_DETACH_PATCHED
    if _OTEL_DETACH_PATCHED:
        return

    try:
        from opentelemetry import context as otel_context

        runtime_context = otel_context._RUNTIME_CONTEXT

        def safe_detach(token):
            try:
                runtime_context.detach(token)
            except ValueError:
                pass
            except Exception as exc:
                logger.debug("Ignored OpenTelemetry context detach error", error=str(exc))

        otel_context.detach = safe_detach
        _OTEL_DETACH_PATCHED = True
    except Exception as exc:
        logger.debug("Could not patch OpenTelemetry context detach", error=str(exc))


def _create_langfuse_callback(trace_name: str) -> BaseCallbackHandler | None:
    """Create a Langfuse LangChain callback when tracing is enabled."""
    if not settings.LANGFUSE_ENABLED:
        return None

    try:
        from langfuse.langchain import CallbackHandler

        _ensure_langfuse_client()
        logger.info("Langfuse callback handler initialized", trace_name=trace_name)
        return CallbackHandler(public_key=settings.LANGFUSE_PUBLIC_KEY or None)
    except ImportError:
        logger.warning("Langfuse is enabled but package is not installed.")
    except Exception as exc:
        logger.warning("Langfuse callback disabled due to init error", error=str(exc))
    return None


def _ensure_langfuse_client() -> None:
    """Initialize the Langfuse SDK once so CallbackHandler can resolve the client."""
    global _LANGFUSE_CLIENT_READY
    if _LANGFUSE_CLIENT_READY:
        return

    from langfuse import Langfuse

    _configure_langfuse_env()
    _patch_opentelemetry_detach_for_async_langfuse()
    Langfuse(
        public_key=settings.LANGFUSE_PUBLIC_KEY or None,
        secret_key=settings.LANGFUSE_SECRET_KEY or None,
        host=settings.LANGFUSE_HOST,
        tracing_enabled=True,
    )
    _LANGFUSE_CLIENT_READY = True


def _build_agent_config(
    trace_name: str,
    metadata: dict[str, Any] | None,
    callbacks: list[BaseCallbackHandler],
) -> dict[str, Any]:
    """Build LangChain config with stable trace metadata."""
    config: dict[str, Any] = {
        "run_name": trace_name,
        "metadata": {
            "langfuse_tags": ["agent-service", "langgraph"],
            "trace_name": trace_name,
            **(metadata or {}),
        },
    }
    if callbacks:
        config["callbacks"] = callbacks
    return config


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
        metadata: dict[str, Any] | None = None,
    ) -> dict:
        """Invoke agent asynchronously without blocking event loop."""
        callbacks = []
        if langfuse_callback := _create_langfuse_callback(trace_name):
            callbacks.append(langfuse_callback)

        agent = create_agent(
            model=self._llm,
            tools=tools,
            system_prompt=system_prompt,
        )

        try:
            result = await agent.ainvoke(
                {"messages": [{"role": "user", "content": prompt}]},
                config=_build_agent_config(trace_name, metadata, callbacks),
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
