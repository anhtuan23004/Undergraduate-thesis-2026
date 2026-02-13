"""API routes for skill-based agent orchestrator."""
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from core.orchestrator import AgentOrchestrator, OrchestratorConfig, SkillInfo

router = APIRouter(tags=["skills"])

# Global orchestrator instance
_orchestrator: Optional[AgentOrchestrator] = None


def get_orchestrator() -> AgentOrchestrator:
    """Get or create the orchestrator singleton."""
    global _orchestrator
    if _orchestrator is None:
        config = OrchestratorConfig(skills_dir="./skills")
        _orchestrator = AgentOrchestrator(config=config)
    return _orchestrator


class SkillResponse(BaseModel):
    """Response model for a skill."""
    name: str
    description: str
    version: str
    author: Optional[str] = None
    tags: List[str] = []
    tools_allowed: List[str] = []


class ProcessRequest(BaseModel):
    """Request to process a user input."""
    input: str = Field(..., description="User input to process")
    skill_name: Optional[str] = Field(None, description="Optional specific skill to use")
    conversation_history: List[Dict[str, str]] = Field(
        default_factory=list,
        description="Previous conversation messages"
    )


class ProcessResponse(BaseModel):
    """Response from processing."""
    success: bool
    output: str
    error: Optional[str] = None
    skill_used: Optional[str] = None
    tool_calls_count: int = 0
    execution_time_ms: float = 0.0


class ExecuteSkillRequest(BaseModel):
    """Request to execute a specific skill."""
    skill_name: str = Field(..., description="Name of skill to execute")
    input: str = Field(..., description="Input for the skill")
    working_directory: Optional[str] = Field(None, description="Working directory")


@router.get("/", response_model=List[SkillResponse])
async def list_skills() -> List[SkillResponse]:
    """List all available skills."""
    orchestrator = get_orchestrator()
    skills = await orchestrator.discover_skills()

    return [
        SkillResponse(
            name=s.name,
            description=s.description,
            version=s.version,
            author=s.author,
            tags=s.tags,
            tools_allowed=s.tools_allowed
        )
        for s in skills
    ]


@router.get("/{skill_name}", response_model=SkillResponse)
async def get_skill(skill_name: str) -> SkillResponse:
    """Get details of a specific skill."""
    orchestrator = get_orchestrator()
    await orchestrator.discover_skills()

    skill = orchestrator.discovery.get_skill(skill_name)
    if not skill:
        raise HTTPException(status_code=404, detail=f"Skill '{skill_name}' not found")

    return SkillResponse(
        name=skill.name,
        description=skill.description,
        version=skill.version,
        author=skill.author,
        tags=skill.tags,
        tools_allowed=skill.tools_allowed
    )


@router.post("/process", response_model=ProcessResponse)
async def process_request(request: ProcessRequest) -> ProcessResponse:
    """Process a user request using the orchestrator.

    The orchestrator will:
    1. Route to the appropriate skill (if skill_name not provided)
    2. Execute the skill with tool calling
    3. Return the result
    """
    orchestrator = get_orchestrator()

    try:
        result = await orchestrator.process(
            user_input=request.input,
            skill_name=request.skill_name,
            conversation_history=request.conversation_history
        )

        return ProcessResponse(
            success=result.success,
            output=result.output,
            error=result.error,
            skill_used=request.skill_name,  # Could also return detected skill
            tool_calls_count=result.tool_calls_count,
            execution_time_ms=result.execution_time_ms
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/execute", response_model=ProcessResponse)
async def execute_skill(request: ExecuteSkillRequest) -> ProcessResponse:
    """Execute a specific skill with input."""
    orchestrator = get_orchestrator()

    try:
        result = await orchestrator.process(
            user_input=request.input,
            skill_name=request.skill_name,
            working_directory=request.working_directory
        )

        return ProcessResponse(
            success=result.success,
            output=result.output,
            error=result.error,
            skill_used=request.skill_name,
            tool_calls_count=result.tool_calls_count,
            execution_time_ms=result.execution_time_ms
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/reload")
async def reload_skills() -> Dict[str, Any]:
    """Reload all skills from disk."""
    orchestrator = get_orchestrator()
    skills = orchestrator.discovery.reload()

    return {
        "status": "success",
        "skills_count": len(skills),
        "skills": [s.name for s in skills]
    }
