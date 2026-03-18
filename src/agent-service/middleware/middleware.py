"""Middleware definitions for the src2-style runtime."""

from typing import Callable

from langchain.agents.middleware import AgentMiddleware, ModelRequest, ModelResponse
from langchain.messages import SystemMessage

from skills import SKILLS
from tools.skill_loading import load_skill


class SkillMiddleware(AgentMiddleware):
    """Inject available skills into the active system prompt."""

    tools = [load_skill]

    def __init__(self):
        skills_list = []
        for skill in SKILLS:
            skills_list.append(f"- **{skill['name']}**: {skill['description']}")
        self.skills_prompt = "\n".join(skills_list)

    def wrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], ModelResponse],
    ) -> ModelResponse:
        skills_addendum = (
            f"\n\n## Available Skills\n\n{self.skills_prompt}\n\n"
            "If the user request matches any skill listed above, call the "
            "load_skill tool before answering. Use load_skill to fetch the "
            "full skill instructions and follow them in your response."
        )

        new_content = list(request.system_message.content_blocks) + [
            {"type": "text", "text": skills_addendum}
        ]
        new_system_message = SystemMessage(content=new_content)
        modified_request = request.override(system_message=new_system_message)
        return handler(modified_request)
