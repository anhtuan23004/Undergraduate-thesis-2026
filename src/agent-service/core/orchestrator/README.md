# AI Agent Orchestrator

A **Claude Agent Skills-inspired** system using LangGraph for orchestration. Each agent has dedicated skills (domain-specific capabilities) defined in markdown files with YAML frontmatter.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    AgentOrchestrator                        │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐    │
│  │   Router    │───▶│  Executor   │───▶│   Output    │    │
│  └─────────────┘    └─────────────┘    └─────────────┘    │
│         │                   │                             │
│         ▼                   ▼                             │
│  ┌─────────────┐    ┌─────────────┐                       │
│  │   Skills    │    │   Tools     │                       │
│  │  Discovery  │    │  Registry   │                       │
│  └─────────────┘    └─────────────┘                       │
└─────────────────────────────────────────────────────────────┘
```

### Components

1. **SkillDiscovery** (`discovery.py`)
   - Scans `./skills/` directory for subdirectories
   - Parses `SKILL.md` files with YAML frontmatter
   - Extracts metadata: name, description, tools_allowed, etc.

2. **SkillExecutor** (`executor.py`)
   - Loads SKILL.md instructions into LLM context
   - Manages tool calling loop (up to max_iterations)
   - Handles tool execution and result formatting

3. **AgentOrchestrator** (`orchestrator.py`)
   - LangGraph-based workflow: Route → Execute → Complete
   - Routes requests to appropriate skills
   - Manages execution state

4. **ToolRegistry** (`tools.py`)
   - Provides tools: `bash_exec`, `file_read`, `file_write`, `computer_use`
   - Filters tools based on skill's `tools_allowed` list
   - Handles tool execution with proper error handling

## Skill Structure

Each skill is a directory containing a `SKILL.md` file:

```
skills/
├── web_search/
│   └── SKILL.md
├── code_analysis/
│   └── SKILL.md
└── file_organizer/
    └── SKILL.md
```

### SKILL.md Format

```markdown
---
name: web_search
description: Search the web for information
tools_allowed: [bash_exec, file_write]
version: "1.0"
author: "AI Team"
tags: [search, web]
---

# Web Search Skill

Instructions for the skill...

## When to Use

Describe when this skill should be used.

## Instructions

1. Step one
2. Step two
3. Step three

## Example Tool Usage

```
bash_exec {
  "command": "curl ...",
  "timeout": 30
}
```
```

## Usage

### Python API

```python
from core.orchestrator import AgentOrchestrator

# Initialize
orchestrator = AgentOrchestrator()

# Discover skills
skills = await orchestrator.discover_skills()

# Process a request (auto-routing)
result = await orchestrator.process("Search for Python tutorials")

# Or use specific skill
result = await orchestrator.process(
    "Search for Python tutorials",
    skill_name="web_search"
)

print(result.output)
print(f"Tool calls: {result.tool_calls_count}")
```

### HTTP API

```bash
# List all skills
curl http://localhost:8000/api/v1/skills/

# Process a request
curl -X POST http://localhost:8000/api/v1/skills/process \
  -H "Content-Type: application/json" \
  -d '{
    "input": "Search for Python tutorials",
    "skill_name": "web_search"
  }'

# Execute specific skill
curl -X POST http://localhost:8000/api/v1/skills/execute \
  -H "Content-Type: application/json" \
  -d '{
    "skill_name": "web_search",
    "input": "Search for Python tutorials"
  }'

# Reload skills
curl -X POST http://localhost:8000/api/v1/skills/reload
```

## Creating a New Skill

1. Create a new directory under `./skills/`:
   ```bash
   mkdir skills/my_new_skill
   ```

2. Create `SKILL.md` with YAML frontmatter:
   ```markdown
   ---
   name: my_new_skill
   description: What this skill does
   tools_allowed: [bash_exec, file_read, file_write]
   version: "1.0"
   tags: [utility]
   ---

   # My New Skill

   Instructions here...
   ```

3. Reload skills or restart the service

## Available Tools

| Tool | Description | Parameters |
|------|-------------|------------|
| `bash_exec` | Execute bash commands | `command`, `working_dir`, `timeout`, `env_vars` |
| `file_read` | Read file contents | `path`, `limit` |
| `file_write` | Write to files | `path`, `content`, `append` |
| `computer_use` | Simulate cursor/keyboard (placeholder) | `action`, `text`, `x`, `y`, `key` |

## Configuration

```python
from core.orchestrator import AgentOrchestrator, OrchestratorConfig

config = OrchestratorConfig(
    skills_dir="./skills",          # Path to skills directory
    max_iterations=10,               # Max tool calling loops
    default_skill="web_search",      # Fallback skill
    routing_prompt="..."             # Custom routing prompt
)

orchestrator = AgentOrchestrator(config=config)
```

## Testing

```bash
# Run orchestrator tests
pytest tests/test_orchestrator.py -v

# Run demo
python examples/orchestrator_demo.py
```

## Example Skills Included

1. **web_search** - Search the web using curl
2. **code_analysis** - Analyze code files for quality
3. **file_organizer** - Organize files by type/date
