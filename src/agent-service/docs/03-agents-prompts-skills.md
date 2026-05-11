# Agents, Prompts, Skills

Folder `agents/`, `prompts/`, `skills/`, và `tools/` tạo thành agent runtime. Mỗi LangGraph agent node được tạo bởi factory, nhận `GraphState`, build prompt tiếng Việt, nạp system prompt + skill context, gọi LLM qua LangChain agent, parse JSON, validate schema, rồi ghi audit.

## Module map

| Module/folder | Logic chính |
| --- | --- |
| `agent.py` | `LangGraphLLMClient`, Gemini model, LangChain `create_agent`, optional Langfuse tracing |
| `agents/node_specs.py` | Registry role metadata cho Completeness, Quality, Final Decision, Verifier |
| `agents/factory.py` | Tạo LangGraph agent node từ `AgentNodeSpec` và shared runtime |
| `agents/prompt_builders.py` | Build user prompt từ `GraphState` cho từng agent |
| `agents/helpers.py` | Load system prompt, tạo history entry, error state |
| `agents/output_parsing.py` | Extract message content, strip JSON fences, parse JSON |
| `agents/audit.py` | Insert audit log vào MongoDB `audit_logs` |
| `tools/skill_loader.py` | Tự động discover `scripts/tool.py` trong `skills/<agent>` và `skills/shared` |
| `prompts/*.md` | System prompt chính cho từng agent |
| `skills/**/SKILL.md` | Mô tả tool/context được inject vào prompt |
| `skills/**/scripts/tool.py` | LangChain tool implementation |

## Agent node specification flow

`AgentNodeSpec` là source of truth cho metadata của một agent role. Factory không còn nhận nhiều primitive string rời; public role factories chỉ lookup spec rồi gọi shared runtime.

| Role | Skill name | Prompt file | Output key | Schema | Active stage | Review stage on `accept_with_edit` |
| --- | --- | --- | --- | --- | --- | --- |
| `completeness` | `completeness_agent` | `prompts/completeness_agent.md` | `agent_1_result` | `AssessmentOutput` | `completeness` | `completeness` |
| `quality` | `quality_agent` | `prompts/quality_agent.md` | `agent_2_result` | `AssessmentOutput` | `quality` | `quality` |
| `decision` | `decision_agent` | `prompts/final_agent.md` | `final_result` | `FinalDecisionOutput` | `final` | `none` |
| `verifier` | `verifier_agent` | `prompts/verifier_agent.md` | `verifier_result` | `VerifierOutput` | `none` | `none` |

```mermaid
flowchart TD
    RoleFactory["Completeness/Quality/Decision/Verifier factory"] --> Lookup["agent_node_spec(role)"]
    Lookup --> Spec["AgentNodeSpec"]
    Spec --> Factory["AgentFactory.create_agent_with_skills(spec)"]
    Spec --> Skill["skill_name"]
    Spec --> PromptName["prompt_name"]
    Spec --> OutputKey["output_key"]
    Spec --> Schema["schema_class"]
    Spec --> PromptBuilder["prompt_builder"]
    Spec --> Stage["active_stage + review_stage_on_accept_with_edit"]
    Factory --> Node["agent_node(state)"]
```

`AgentNodeSpec` không sở hữu graph transition. Các quyết định route vẫn thuộc `graphs.workflow_policy`; spec chỉ mô tả cách build một agent node và state update trực tiếp mà node trả về.

## Agent invocation pipeline

```mermaid
sequenceDiagram
    autonumber
    participant Graph as LangGraph node
    participant Spec as AgentNodeSpec
    participant Factory as AgentFactory
    participant Loader as skill_loader
    participant Prompt as prompt_builders
    participant LLM as LangGraphLLMClient
    participant Parser as output_parsing
    participant Schema as Pydantic schema
    participant Mongo as audit_logs

    Factory->>Spec: agent_node_spec(role)
    Factory->>Loader: load_agent_skills(spec.skill_name)
    Loader-->>Factory: tools + skill_contexts
    Factory->>Factory: load_system_prompt(spec.prompt_name) + schema instruction
    Graph->>Factory: agent_node(state)
    Factory->>Prompt: spec.prompt_builder(state, spec.display_name)
    Factory->>LLM: invoke_agent(prompt, tools, system_prompt, trace_name)
    LLM->>LLM: create_agent(model=Gemini, tools=tools)
    LLM-->>Factory: raw messages
    Factory->>Parser: extract_agent_content(raw_result)
    Parser-->>Factory: content string
    Factory->>Parser: parse_json_response(content)
    Parser-->>Factory: parsed dict
    Factory->>Schema: spec.schema_class.model_validate(parsed dict)
    Schema-->>Factory: validated model_dump
    Factory->>Mongo: save_agent_audit_log(...)
    Factory-->>Graph: {spec.output_key, history, current_step, active/review stage}
```

## Agent factories

Các class `CompletenessAgentFactory`, `QualityAgentFactory`, `DecisionAgentFactory`, và `VerifierAgentFactory` là compatibility wrappers cho call sites hiện tại như `build_claim_workflow`. Chúng không còn override prompt builder hoặc chứa mapping literal riêng; mapping nằm trong `AGENT_NODE_SPECS`.

## Prompt composition

System prompt:

1. Read `prompts/{spec.prompt_name}.md`.
2. Replace `{{skill_contexts}}` bằng nội dung `SKILL.md` đã load.
3. Append `<output_format>` chứa Pydantic JSON schema.
4. Bỏ `is_auto_reviewed` khỏi schema instruction để LLM không tự quyết cờ nội bộ.

User prompt:

```mermaid
flowchart TD
    State["GraphState"] --> AgentType{"agent"}
    AgentType -->|"Completeness"| CP["claim_id, policy_number, input_file,<br/>ocr_stage, extracted_documents,<br/>history_summary"]
    AgentType -->|"Quality"| QP["claim_id, policy_number,<br/>extracted_documents,<br/>history_summary"]
    AgentType -->|"Final"| FP["claim_id, policy_number,<br/>agent_1_result, agent_2_result,<br/>human_review_result"]
    AgentType -->|"Verifier"| VP["primary_assessment,<br/>extracted evidence,<br/>extracted_documents"]
```

Verifier prompt không tự suy luận `agent_1_result`/`agent_2_result`. Nó gọi `workflow_policy.review_target_from_state(state)` để lấy assessment target giống Agent Review routing.

## Skill loading

`load_agent_skills(agent_name)` có cache theo `agent_name`. Loader đọc hai nơi:

- `skills/<agent-name-kebab>/...`
- `skills/shared/...`

Mỗi skill folder có thể cung cấp:

- `SKILL.md`: context được inject vào system prompt.
- `scripts/tool.py`: module được import động để tìm một `StructuredTool` hoặc `LangChainBaseTool`.

```mermaid
flowchart TD
    Call["load_agent_skills(agent_name)"] --> Cache{"in _skill_cache?"}
    Cache -->|"yes"| Cached["return cached tools/context"]
    Cache -->|"no"| Root["skills root"]
    Root --> AgentDir["skills/<agent-name-kebab>"]
    Root --> SharedDir["skills/shared"]
    AgentDir --> Recursive["sorted child skill dirs"]
    SharedDir --> Recursive
    Recursive --> ToolFile{"scripts/tool.py exists?"}
    ToolFile -->|"no"| Skip["skip tool, warn"]
    ToolFile -->|"yes"| Import["importlib spec_from_file_location"]
    Import --> Find["find StructuredTool/BaseTool attr"]
    Find --> ReadSkill["read SKILL.md without frontmatter"]
    ReadSkill --> Context["append Available Tool context"]
    Context --> Store["cache (tools, combined_contexts)"]
```

## Output parsing and validation

`parse_json_response` chấp nhận JSON thuần hoặc markdown fenced JSON. Nếu parse lỗi, helper trả fallback reject-like payload. Với các agent có schema, factory validate ngay bằng Pydantic; validation fail trở thành agent error state.

```mermaid
flowchart TD
    Raw["raw LangChain result"] --> Extract["extract_agent_content"]
    Extract --> ContentType{"message.content type"}
    ContentType -->|"str"| Text["strip string"]
    ContentType -->|"list blocks"| Join["join text blocks"]
    ContentType -->|"other"| Coerce["str(last_message)"]
    Text --> Parse["parse_json_response"]
    Join --> Parse
    Coerce --> Parse
    Parse --> Fence["strip ```json fence if present"]
    Fence --> JSON{"json.loads ok?"}
    JSON -->|"yes"| Validate["schema.model_validate"]
    JSON -->|"no"| Default["default parse error payload"]
    Validate -->|"ok"| StateUpdate["agent result state update"]
    Validate -->|"fail"| ErrorState["create_agent_error_state"]
```

## Audit behavior

Agent audit log là side effect không làm fail workflow nếu Mongo insert lỗi. `save_agent_audit_log` dùng `asyncio.to_thread` để insert vào collection `audit_logs`; nếu insert fail, exception bị catch và ghi warning log `Failed to save audit log`.

```mermaid
erDiagram
    AUDIT_LOG {
        string run_id
        string claim_id
        string step_name
        string agent_name
        object result_json
        datetime timestamp
    }
```

## Current risk notes

`AgentFactory.create_agent_with_skills` nằm trên luồng tạo node trung tâm của `build_claim_workflow`, nên thay đổi ở đây có blast radius cao. GitNexus có thể báo risk `critical` cho refactor trong factory ngay cả khi public graph topology không đổi.

Các guardrail bắt buộc khi sửa agent runtime:

- Giữ public role factory methods nếu chưa refactor `graphs/claim_workflow.py`.
- Giữ output keys trong `GraphState`: `agent_1_result`, `agent_2_result`, `final_result`, `verifier_result`.
- Khi thêm role mới, thêm spec, prompt builder, schema, prompt file, skill folder nếu cần, và tests cho spec/factory lifecycle.
- Chạy ít nhất:
  - `python -m pytest src/agent-service/tests/test_agent_node_specs.py src/agent-service/tests/test_agent_factory.py src/agent-service/tests/test_agent_prompt_builders.py src/agent-service/tests/test_agent_review.py src/agent-service/tests/test_routing.py -q`
  - `STRICT_SKILL_LOADING=true python -m pytest src/agent-service/tests -q`
