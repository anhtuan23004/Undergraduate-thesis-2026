# Workflow Graph

Folder `graphs/` chứa state machine nghiệp vụ của claim workflow. Graph chạy theo LangGraph, có checkpoint MongoDB, và dừng trước node `human_review` để UI/API inject quyết định của thẩm định viên.

## Module map

| Module | Logic chính |
| --- | --- |
| `graphs/state.py` | `GraphState` TypedDict, các field lifecycle và kết quả agent |
| `graphs/constants.py` | Node names, stage names, workflow statuses, severity constants |
| `graphs/claim_workflow.py` | Build LangGraph, đăng ký nodes, conditional edges, compile interrupt |
| `graphs/workflow_policy.py` | Policy tập trung stage metadata, result-key mapping, decision normalization, routing decision |
| `graphs/routing.py` | Adapter mỏng giữ các routing function mà LangGraph đang gọi |
| `graphs/ocr_extraction.py` | OCR phase 2 sau khi Completeness approve phase 1 |
| `graphs/agent_review.py` | Tự duyệt `accept_with_edit` bằng hard constraints + VerifierAgent |
| `graphs/human_review.py` | Virtual interrupt node; chạy no-op sau khi API resume |

## Graph topology

```mermaid
flowchart TD
    Start((START)) --> C["completeness_check<br/>CompletenessAgent"]

    C --> RC{"route_after_completeness"}
    RC -->|"accept"| OCR["ocr_extraction<br/>OCR phase 2"]
    RC -->|"accept_with_edit"| AR["agent_review<br/>Verifier/hard constraints"]
    RC -->|"reject"| F["final_decision<br/>FinalAgent"]

    OCR --> RO{"route_after_ocr_extraction"}
    RO -->|"phase2_extracted"| Q["quality_check<br/>QualityAgent"]
    RO -->|"error / no phase2"| F

    Q --> RQ{"route_after_quality"}
    RQ -->|"accept or reject"| F
    RQ -->|"accept_with_edit"| AR

    AR --> RAR{"route_after_agent_review"}
    RAR -->|"completeness auto-reviewed"| OCR
    RAR -->|"quality auto-reviewed"| F
    RAR -->|"not auto-reviewed"| H["human_review<br/>interrupt before node"]

    F --> RF{"route_after_final_review"}
    RF -->|"always final sign-off"| H

    H --> RH{"route_after_human_review"}
    RH -->|"completeness edit"| C
    RH -->|"completeness approve"| OCR
    RH -->|"completeness reject"| F
    RH -->|"quality edit"| Q
    RH -->|"quality approve/reject"| F
    RH -->|"final edit"| Q
    RH -->|"final approve/reject"| End((END))
```

## Build and compile logic

`build_claim_workflow(llm_client, checkpointer=None)` tạo các factory. Các factory này là wrapper mỏng quanh `agents.node_specs.AGENT_NODE_SPECS`; role metadata như prompt name, skill name, output key, schema và active/review stage nằm trong `AgentNodeSpec`.

| Factory | Node | Output key |
| --- | --- | --- |
| `CompletenessAgentFactory` | `completeness_check` | `agent_1_result` |
| `QualityAgentFactory` | `quality_check` | `agent_2_result` |
| `DecisionAgentFactory` | `final_decision` | `final_result` |
| `AgentReviewNode` | `agent_review` | update `agent_1_result` hoặc `agent_2_result` |
| `HumanReviewNode` | `human_review` | clear pending review sau resume |
| `run_ocr_extraction` | `ocr_extraction` | update `extracted_documents` phase 2 |

```mermaid
flowchart TD
    Build["build_claim_workflow"] --> RoleFactory["Completeness/Quality/Decision factory"]
    RoleFactory --> Spec["agents.node_specs.AgentNodeSpec"]
    Spec --> AgentFactory["AgentFactory.create_agent_with_skills(spec)"]
    AgentFactory --> Node["LangGraph agent node"]
    Node --> Output["GraphState output key<br/>from spec.output_key"]
```

Graph compile:

```mermaid
flowchart LR
    Builder["StateGraph(GraphState)"] --> Nodes["add_node(...)"]
    Nodes --> Entry["set_entry_point(completeness_check)"]
    Entry --> Edges["add_conditional_edges(...)"]
    Edges --> Checkpointer{"checkpointer provided?"}
    Checkpointer -->|"yes"| MongoSaver["MongoDBSaver"]
    Checkpointer -->|"no"| MemorySaver["MemorySaver"]
    MongoSaver --> Interrupts["interrupt_before"]
    MemorySaver --> Interrupts
    Interrupts --> Human["human_review always"]
    Interrupts --> PauseFlag{"PAUSE_AT_EACH_STAGE?"}
    PauseFlag -->|"true"| Extra["quality_check + final_decision"]
    PauseFlag -->|"false"| Compile["compile"]
    Extra --> Compile
```

## Workflow routing policy

`graphs/workflow_policy.py` là điểm tập trung routing policy của insurance claim workflow. Module này sở hữu stage metadata, chuẩn hóa decision, chọn target cho verifier gate, và quyết định node tiếp theo cho các nhánh agent review/human review/OCR.

- `routing.py` là adapter để LangGraph gọi các function như `route_after_completeness`, `route_after_agent_review`, `route_after_human_review`.
- `workflow_policy.py` sở hữu stage metadata và routing rules.
- `AgentReviewNode` gọi `review_target_from_state(state)` để lấy `stage`, `result_key`, và `agent_result`.
- `review_stage_from_state` ưu tiên `review_stage`, rồi fallback qua `current_step`/`final_result` cho checkpoint cũ.

Stage metadata hiện có:

| Stage | Result key | Edited result key | Accept route | Reject route | Human edit route | Agent review? |
| --- | --- | --- | --- | --- | --- | --- |
| `completeness` | `agent_1_result` | `edited_agent_1_result` | `ocr_extraction` nếu OCR phase 1, ngược lại `quality_check` | `final_decision` | `completeness_check` | Yes |
| `quality` | `agent_2_result` | `edited_agent_2_result` | `final_decision` | `final_decision` | `quality_check` | Yes |
| `final` | `final_result` | none | `human_review` | `human_review` | `quality_check` | No |

```mermaid
flowchart TD
    State["GraphState"] --> Policy["workflow_policy"]
    Policy --> Stage["review_stage_from_state"]
    Policy --> Meta["StagePolicy metadata"]
    Meta --> ResultKey["result_key / edited_result_key"]
    Meta --> Next["next_after_* routes"]

    Routing["routing.py adapter"] --> Policy
    AgentReview["AgentReviewNode"] --> Target["review_target_from_state"]
    Target --> ResultKey
    Target --> AgentResult["selected agent result"]
```

Policy là Python module explicit, không phải runtime plugin/config framework. Khi thêm stage mới, cập nhật `StagePolicy`, routing tests, và các consumer liên quan như UI timeline nếu stage cần hiển thị riêng.

## Routing by decision and severity

`workflow_policy.py` chuẩn hóa quyết định từ agent output:

- Nếu output có `decision`, dùng trực tiếp.
- Nếu thiếu `decision`, suy ra từ `valid` và issue severity.
- `critical/high` được xem là reject-level escalation.
- Issue thấp hơn có thể thành `accept_with_edit`.

```mermaid
flowchart TD
    Result["agent result"] --> HasDecision{"decision exists?"}
    HasDecision -->|"yes"| Decision["accept / reject / accept_with_edit"]
    HasDecision -->|"no"| Valid{"valid true?"}
    Valid -->|"true"| Accept["accept"]
    Valid -->|"false"| Severity{"has critical/high issue?"}
    Severity -->|"yes"| Reject["reject"]
    Severity -->|"no"| Edit["accept_with_edit"]
```

## Agent Review logic

`AgentReviewNode` chỉ xử lý stage có `supports_agent_review=True` trong `StagePolicy`, hiện là `completeness` và `quality`. Nó không tự sửa kết quả; nó chỉ đánh dấu `is_auto_reviewed=True` nếu đủ an toàn.

Verifier gate không tự biết `agent_1_result` hay `agent_2_result`. Nó dùng `review_target_from_state(state)` để lấy đúng target:

| Policy output | AgentReviewNode dùng để |
| --- | --- |
| `stage` | ghi `current_step`, `review_stage`, history |
| `result_key` | update lại đúng state key với `is_auto_reviewed` |
| `result` | đọc confidence, issues, suggested updates, evidence |
| `active_stage_after_auto_review` | set `active_stage` sau khi verifier pass |

Điều kiện tự duyệt:

| Check | Ý nghĩa |
| --- | --- |
| `total_claim_amount < AGENT_REVIEW_AMOUNT_THRESHOLD` | Hồ sơ không vượt ngưỡng tiền cấu hình |
| Không có severity `critical/high/medium` | Không có cảnh báo cần người xem |
| Có `suggested_updates` | Có đề xuất cụ thể để xác thực |
| `confidence_score >= AGENT_REVIEW_CONFIDENCE_THRESHOLD` | Agent chính đủ tự tin |
| Verifier verdict `pass` và không có contradictions | Xác minh chéo không phát hiện mâu thuẫn |

```mermaid
flowchart TD
    AR["AgentReviewNode.run"] --> Target["workflow_policy.review_target_from_state"]
    Target --> Pick["stage + result_key + selected result"]
    Pick --> Amount["parse total_claim_amount"]
    Amount --> Hard{"safe amount<br/>safe severity<br/>has suggestions?"}
    Hard -->|"no"| Escalate1["escalate to human<br/>reason hard_constraints_failed"]
    Hard -->|"yes"| Confidence{"confidence >= threshold?"}
    Confidence -->|"no"| Escalate2["escalate to human<br/>reason low_confidence"]
    Confidence -->|"yes"| Verifier["VerifierAgent"]
    Verifier --> Verdict{"verdict pass<br/>and contradictions empty?"}
    Verdict -->|"yes"| Auto["mark is_auto_reviewed=True<br/>workflow_status running"]
    Verdict -->|"no"| Escalate3["escalate to human<br/>verifier_failed/contradictions"]

    Auto --> RouteAuto{"route_after_agent_review"}
    RouteAuto -->|"completeness"| OCR["ocr_extraction"]
    RouteAuto -->|"quality"| Final["final_decision"]
    Escalate1 --> Human["human_review interrupt"]
    Escalate2 --> Human
    Escalate3 --> Human
```

## Human review logic

Graph được compile với `interrupt_before=["human_review"]`, nên node `HumanReviewNode.run` chỉ chạy sau khi API đã update `human_review_result`.

```mermaid
sequenceDiagram
    autonumber
    participant Graph
    participant API
    participant UI
    participant Reviewer

    Graph->>Graph: route to human_review
    Graph-->>API: snapshot.next = human_review
    API-->>UI: pending_human_review=true, paused=true
    UI-->>Reviewer: show HITL panel
    Reviewer->>UI: approve/reject/edit
    UI->>API: POST /resume/{run_id}
    API->>Graph: aupdate_state(human_review_result, as_node=human_review)
    API->>Graph: ainvoke(None)
    Graph->>Graph: HumanReviewNode.run clears pending flag
    Graph->>Graph: route_after_human_review decides next node
```

## OCR phase 2 node

`ocr_extraction.py` nhận `documents` từ OCR phase 1, lọc lại classification fields để tránh lẫn `extracted_data`, rồi gọi `prepare_ocr_phase2_result(...)`. Nếu lỗi, nó tạo `agent_2_result` reject với issue `OCR_EXTRACTION_FAILED` để graph vẫn có thể route về `final_decision`.

```mermaid
flowchart TD
    Extract["run_ocr_extraction"] --> Docs["extracted_documents.documents"]
    Docs --> Clean["keep document_code/name<br/>suggested_*<br/>start_page/end_page"]
    Clean --> Empty{"phase1_documents empty?"}
    Empty -->|"yes"| Error["agent_2_result reject<br/>OCR_EXTRACTION_FAILED"]
    Empty -->|"no"| Phase2["prepare_ocr_phase2_result"]
    Phase2 --> Success["extracted_documents = phase2_result<br/>ocr_stage=phase2_extracted<br/>active_stage=quality"]
    Phase2 --> Failure["error branch<br/>agent_2_result reject"]
```
