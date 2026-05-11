# Streamlit UI

Folder `interfaces/web/` là UI vận hành thủ công cho claim workflow. UI upload tài liệu, gọi API streaming để hiện tiến trình theo từng node, hiển thị bằng chứng/issue/suggested updates, và gửi quyết định Human-in-the-Loop.

## Module map

| Module | Logic chính |
| --- | --- |
| `interfaces/web/app.py` | Entry point Streamlit, session state, action handlers, auto polling, render flow |
| `interfaces/web/api_client.py` | HTTP client cho API JSON, upload multipart, SSE parser |
| `interfaces/web/components.py` | UI components, timeline, HITL panel, evidence/issues/medical findings |
| `interfaces/web/README.md` | Hướng dẫn chạy UI và endpoint liên quan |

## UI application flow

```mermaid
flowchart TD
    Main["main()"] --> Page["st.set_page_config"]
    Page --> Init["init_session_state"]
    Init --> Theme["render_brand_theme"]
    Theme --> Sidebar["render_sidebar"]
    Sidebar --> Header["render_app_header"]
    Header --> Content["render_main_content"]

    Content --> HasData{"workflow_state_data exists?"}
    HasData -->|"no"| Form["render_claim_submission"]
    HasData -->|"yes"| PendingContinue{"pending_paused_continue_request?"}
    PendingContinue -->|"yes"| Continue["handle_continue_workflow"]
    PendingContinue -->|"no"| Refresh["Refresh button + render_auto_polling"]
    Refresh --> Monitor["render_monitoring"]
    Monitor --> UIState{"get_ui_state"}
    UIState -->|"WAITING_FOR_HUMAN"| HITL["render_human_review_panel"]
    UIState -->|"COMPLETED"| Final["render_final_dashboard"]
    UIState -->|"ERROR"| Error["render_error_state + retry continue"]
    UIState -->|"PROCESSING"| Paused{"paused and not human?"}
    Paused -->|"yes"| ContinueButton["Continue paused stage button"]
    Paused -->|"no"| End["wait / auto poll"]
```

## Session state keys

| Key | Vai trò |
| --- | --- |
| `current_run_id` | Run đang được xem/chạy |
| `workflow_state_data` | Response state mới nhất từ API/SSE |
| `run_history` | Danh sách run gần đây trong sidebar |
| `api_base_url` | Base URL agent-service |
| `client` | Cached `APIClient` theo base URL |
| `auto_poll_enabled` | Bật/tắt polling khi workflow processing |
| `workflow_action_lock` | Chống double-submit resume |
| `paused_continue_button_disabled` | Disable nút continue khi request pending |
| `pending_paused_continue_request` | Trigger continue trong rerun kế tiếp |
| `refresh_in_flight` | Chặn refresh trùng |

## Upload + streaming workflow

```mermaid
sequenceDiagram
    autonumber
    participant User
    participant App as app.py
    participant Client as APIClient
    participant API as Agent Service API

    User->>App: submit claim form + uploaded_file
    App->>Client: upload_document(name, bytes, mime)
    Client->>API: POST /api/v1/workflows/upload multipart
    API-->>Client: file_path, file_hash
    Client-->>App: upload_result
    App->>Client: start_workflow_stream(claim_id, policy, file_path, file_hash)
    Client->>API: POST /api/v1/workflows/run-stream
    API-->>Client: SSE events
    loop for each SSE event
        Client-->>App: (event_type, payload)
        App->>App: update st.status and workflow_state_data
    end
    App->>App: upsert_run_history and rerun
```

## SSE parser in API client

`APIClient._consume_sse_stream` đọc từng line:

- `event:` cập nhật event type.
- `data:` append data lines.
- Empty line là event boundary, parse JSON và yield `(event_type, payload)`.
- Network error được yield thành `("error", {"error": ...})`.

SSE node map hiện có cả `ocr_extraction`; UI dùng `STEP_LABELS["ocr_extraction"]` để hiển thị bước OCR phase 2 là "Trích xuất OCR chi tiết" trong status stream, nhưng không thêm node này vào timeline chính để tránh đổi layout/pipeline hiển thị tổng quan.

```mermaid
flowchart TD
    Stream["requests response.iter_lines"] --> Line{"line prefix"}
    Line -->|"event:"| SetEvent["event_type = value"]
    Line -->|"data:"| Append["append data_lines"]
    Line -->|"empty"| Boundary{"data_lines exists?"}
    Boundary -->|"yes"| Parse["json.loads(joined data)"]
    Boundary -->|"no"| Next["next line"]
    Parse --> Yield["yield event_type, payload"]
    Yield --> Reset["event_type=message; data_lines=[]"]
    Line -->|"request exception"| Error["yield error event"]
```

## UI state mapping

`components.get_ui_state` map workflow response thành 4 trạng thái chính:

```mermaid
flowchart TD
    Data["state_data"] --> Empty{"empty?"}
    Empty -->|"yes"| Processing["PROCESSING"]
    Empty -->|"no"| Error{"error or workflow_status=error?"}
    Error -->|"yes"| UIError["ERROR"]
    Error -->|"no"| Waiting{"workflow_status=waiting_human<br/>or pending_human_review?"}
    Waiting -->|"yes"| Human["WAITING_FOR_HUMAN"]
    Waiting -->|"no"| Completed{"workflow_status=completed<br/>or final_result exists?"}
    Completed -->|"yes"| Done["COMPLETED"]
    Completed -->|"no"| Processing
```

## Timeline computation

Timeline không chỉ dựa vào `current_step`; nó cũng đọc `agent_1_result`, `agent_2_result`, `human_review_result`, `final_result`, `active_stage`, `review_stage`, và `pending_human_review`.

```mermaid
flowchart TD
    State["workflow state"] --> Init["all steps PENDING"]
    Init --> A1{"agent_1_result?"}
    A1 -->|"yes"| CDone["completeness DONE"]
    Init --> A2{"agent_2_result?"}
    A2 -->|"yes"| QDone["quality DONE"]
    Init --> HReview{"human_review_result<br/>and not pending?"}
    HReview -->|"yes"| HDone["human_review DONE"]
    Init --> Final{"final_result?"}
    Final -->|"yes"| FDone["final_decision DONE<br/>return"]
    Final -->|"no"| Waiting{"waiting_human or pending_human_review?"}
    Waiting -->|"yes"| HWait["human_review WAITING<br/>agent_review DONE if review_stage completeness/quality"]
    Waiting -->|"no"| Current["use active_stage/current_step<br/>to mark ACTIVE"]
```

## Human review panel

HITL panel lấy assessment pending từ state, hiển thị issue/evidence/suggested updates, cho reviewer chọn `approve`, `reject`, hoặc `edit`. Với `edit`, UI mở JSON editor và gửi `edited_result`.

```mermaid
flowchart TD
    HumanUI["render_human_review_panel"] --> Assessment["_get_pending_assessment"]
    Assessment --> Findings["_render_assessment_findings"]
    Findings --> Evidence["_render_evidence_panel"]
    Findings --> Suggestions["_render_suggested_updates"]
    HumanUI --> Decision["radio approve/reject/edit"]
    Decision --> Edit{"decision == edit?"}
    Edit -->|"yes"| JSONEditor["text_area JSON<br/>json.loads validation"]
    Edit -->|"no"| Submit["Continue workflow button"]
    JSONEditor --> Submit
    Submit --> Handler["handle_resume_workflow"]
    Handler --> Client["APIClient.resume_workflow"]
    Client --> API["POST /api/v1/workflows/resume/{run_id}"]
```
