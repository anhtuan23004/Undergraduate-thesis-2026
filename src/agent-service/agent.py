"""LangChain agent runtime."""

from pathlib import Path

from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain_google_genai import ChatGoogleGenerativeAI
from langfuse import get_client
from langfuse.langchain import CallbackHandler

from config import settings
from middleware.middleware import SkillMiddleware
from tools import extract_document, load_skill, lookup_icd, search_medicine

load_dotenv()

langfuse = get_client()
langfuse_handler = CallbackHandler()

llm = ChatGoogleGenerativeAI(
    model=settings.GEMINI_MODEL,
    google_api_key=settings.GEMINI_API_KEY,
    temperature=0,
)

tools = [
    extract_document,
    load_skill,
    search_medicine,
    lookup_icd,
]

# Cache system prompt at module level to avoid repeated file I/O
_SYSTEM_PROMPT = (Path(__file__).parent / "prompts" / "system_prompt.md").read_text(encoding="utf-8")


def load_system_prompt() -> str:
    """Load the cached base system prompt."""
    return _SYSTEM_PROMPT


def run_agent(user_message: str, session_id: str = "default") -> dict:
    """Run the agent with a user message and return raw result."""
    agent = create_agent(
        llm,
        tools=tools,
        system_prompt=load_system_prompt(),
        middleware=[SkillMiddleware()],
    )

    result = agent.invoke(
        {"messages": [{"role": "user", "content": user_message}]},
        config={
            "callbacks": [langfuse_handler],
            "configurable": {"session_id": session_id},
        },
    )

    return result
