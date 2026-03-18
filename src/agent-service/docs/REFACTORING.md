# LangChain v1 Refactoring Guide

This document describes the refactoring of the agent-service to use
LangChain v1's `create_agent` and prebuilt middleware.

## Overview

The refactoring replaces the custom `SkillAgent` base class with LangChain v1's
agent system while maintaining backward compatibility with the existing LangGraph workflow
and medical claim verification capabilities.

## Key Changes

### 1. New Agent System (`core/agent_system/`)

| Component | Purpose | Location |
|-----------|---------|----------|
| `AgentFactory` | Factory for creating agents with middleware | `agent_factory.py` |
| `ToolAdapter` | Bridge between BaseTool and LangChain tools | `agent_factory.py` |
| `LoggingMiddleware` | Observability middleware | `middleware.py` |
| `RetryMiddleware` | Exponential backoff retry logic | `middleware.py` |
| `MetricsMiddleware` | Performance tracking | `middleware.py` |
| `ToolSelectionMiddleware` | Intelligent tool routing | `middleware.py` |
| `TokenTrackingMiddleware` | Token and cost tracking | `middleware.py` |
| `ErrorHandlingMiddleware` | Standardized error handling | `middleware.py` |

### 2. New Workflow Builder (`workflow/graph_v2.py`)

- Uses `AgentFactory` instead of directly instantiating agents
- Maintains same workflow structure and routing logic
- Fully compatible with existing `GraphState` and router

### 3. Updated Requirements

Added LangChain v1 dependencies:
- `langchain>=0.3.0`
- `langchain-core>=0.3.0`
- `langchain-anthropic>=0.3.0` (for agent patterns)

## Migration Path

### Phase 1: Drop-in Replacement (Current)

The v2 graph builder provides a drop-in replacement:

```python
# Before:
from workflow.graph import build_multi_agent_graph

# After (no code change needed - import alias):
from workflow.graph_v2 import build_multi_agent_graph
```

The `build_multi_agent_graph` function in `workflow/graph_v2.py` is an alias
that calls `build_multi_agent_graph_v2()`, maintaining full backward compatibility.

### Phase 2: Gradual Adoption

Gradually adopt middleware features:

1. **Enable Logging Middleware** (default enabled)
   - Automatic logging of all agent operations
   - Integration with structlog

2. **Enable Metrics Middleware** (default enabled)
   - Track execution time, success/failure rates
   - Performance analytics

3. **Enable Token Tracking** (default enabled)
   - Monitor token usage per agent run
   - Cost estimation

4. **Enable Retry Middleware** (default enabled)
   - Automatic retry on transient errors
   - Exponential backoff with jitter

5. **Enable Error Handling** (default enabled)
   - Graceful degradation on permanent errors
   - Standardized error classification

### Phase 3: Full LangChain Integration (Future)

For complete migration to LangChain v1:

1. Replace `LLMClient.generate_with_tools()` with LangChain's native `create_agent()`
2. Use `Runnable.with_config()` for per-invocation configuration
3. Leverage LangChain's `@tool` decorator for tool definitions
4. Use prebuilt middleware from `langchain.agents.middleware`

## Architecture Comparison

### Before (Legacy)

```
┌─────────────────┐
│  SkillAgent    │  Custom implementation
│  (base class)  │  - Manual tool calling loop
│                │  - Manual retry logic
│                │  - Custom state management
└────────┬────────┘
         │
         ├─▶ CompletenessAgent
         ├─▶ QualityAgent
         └─▶ FinalAgent
              │
              ▼
         ┌─────────────┐
         │  LangGraph  │  Custom workflow
         │  Workflow     │  orchestration
         └─────────────┘
```

### After (Refactored)

```
┌──────────────────────────┐
│   AgentFactory        │  LangChain v1 factory
│   + Middleware Stack  │  - Prebuilt middleware
│                     │  - Standard retry logic
│                     │  - Observability built-in
└─────────┬────────────┘
          │
          ├─▶ LoggingMiddleware
          ├─▶ RetryMiddleware
          ├─▶ MetricsMiddleware
          ├─▶ ToolSelectionMiddleware
          ├─▶ TokenTrackingMiddleware
          └─▶ ErrorHandlingMiddleware
                 │
                 ▼
         ┌──────────────────────┐
         │  Agent Nodes        │  LangGraph-compatible
         │  (create_agent)     │  state functions
         └────────┬───────────┘
                  │
          ┌─────────┼─────────┐
          ▼         ▼         ▼
    ┌──────────┐ ┌──────────┐ ┌──────────┐
    │Completeness│ │  Quality  │ │   Final   │
    │   Node    │ │   Node    │ │   Node    │
    └──────────┘ └──────────┘ └──────────┘
```

## Middleware Configuration

All middleware can be configured via `MiddlewareConfig`:

```python
from core.agent_system import MiddlewareConfig, build_middleware_stack

config = MiddlewareConfig(
    enable_logging=True,          # Enable logging (default: True)
    enable_metrics=True,          # Enable metrics (default: True)
    enable_retry=True,           # Enable retry (default: True)
    enable_token_tracking=True,   # Enable token tracking (default: True)
    enable_tool_selection=True,   # Enable tool selection (default: True)
    enable_error_handling=True,    # Enable error handling (default: True)
    max_retries=3,              # Max retry attempts (default: 3)
    max_tokens_per_run=100000,   # Token limit (default: 100000)
)

middleware_stack = build_middleware_stack(config, "MyAgent", tools=my_tools)
```

## Testing

Run the comprehensive test suite:

```bash
# Run all agent system tests
cd src/agent-service
pytest tests/test_agent_system.py -v

# Run with coverage
pytest tests/test_agent_system.py --cov=core/agent_system --cov-report=html
```

## Benefits

1. **Production-Ready Retry Logic**
   - Exponential backoff with jitter
   - Transient vs permanent error classification
   - Configurable retry limits

2. **Enhanced Observability**
   - Automatic logging of all operations
   - Performance metrics tracking
   - Token usage monitoring

3. **Cost Control**
   - Token limit enforcement
   - Cost estimation and capping
   - Usage analytics

4. **Better Error Handling**
   - Graceful degradation on permanent errors
   - Standardized error context
   - Automatic retry for transient failures

5. **Maintained Compatibility**
   - All existing tools work unchanged
   - LangGraph workflow structure preserved
   - Medical claim verification skills intact

## Medical Claim Verification Capabilities

The refactoring preserves all medical claim verification skills:

| Skill | Status |
|--------|--------|
| `check_document_completeness` | ✅ Preserved |
| `check_document_consistency` | ✅ Preserved |
| `check_document_compliance` | ✅ Preserved |
| `check_diagnosis` | ✅ Preserved |
| `check_icd` | ✅ Preserved |
| `check_exclusive_disease` | ✅ Preserved |

Tools remain unchanged and are automatically adapted via `ToolAdapter` for use
with the new LangChain-based agent system.

## Future Enhancements

1. **Full LangChain `create_agent()` Integration**
   - Replace custom agent loop with LangChain's native implementation
   - Use prebuilt middleware from `langchain.agents.middleware`

2. **LangSmith Integration**
   - Automatic tracing via LangSmith
   - Agent performance dashboards

3. **Advanced HITL Patterns**
   - Multi-step approval workflows
   - Parallel review delegation

4. **Custom Middleware Development**
   - Domain-specific middleware for claims processing
   - Policy validation middleware
   - Fraud detection middleware
