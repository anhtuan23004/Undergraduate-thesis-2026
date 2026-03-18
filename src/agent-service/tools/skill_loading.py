"""Tool for loading full skill instructions by name."""

from langchain.tools import tool

from skills import SKILLS


@tool
def load_skill(skill_name: str) -> str:
    """Load the full content of a skill into the agent context."""
    for skill in SKILLS:
        if skill["name"] == skill_name:
            return f"Loaded skill: {skill_name}\n\n{skill['content']}"

    available = ", ".join(s["name"] for s in SKILLS)
    return f"Skill '{skill_name}' not found. Available skills: {available}"
