# Services and Persistence

Folder `services/` chứa logic dùng chung cho API và graph: compiled graph lifecycle, OCR orchestration/cache, file upload policy, response shaping, và MongoDB connection config.

## Module map

| Module | Logic chính |
| --- | --- |
| `services/graph_service.py` | Singleton compiled graph, MongoDBSaver checkpointer, LLM client injection |
| `services/workflow_state.py` | Build initial `GraphState`, build API response, pause/review-stage helpers |
| `services/ocr_service.py` | Gọi OCR v1/v2, cache theo hash, audit OCR result vào MongoDB |
| `services/file_policy.py` | Upload dir, safe filename, metadata validation, path containment |
| `services/mongodb_config.py` | Normalize MongoDB URL và timeout kwargs cho PyMongo |
| `mongodb_client.py` | Shared MongoDB client/collection helpers cho audit/cache |
| `config.py` | Settings/env validation cho toàn service |

## Graph lifecycle and checkpointing

`get_graph()` lazy-load compiled graph một lần trong process. Checkpointer dùng `MongoDBSaver`, nên mỗi workflow dùng `thread_id = run_id` để lưu và resume state.

```mermaid
flowchart TD
    API["API endpoint"] --> GetGraph["get_graph()"]
    GetGraph --> Exists{"_compiled_graph exists?"}
    Exists -->|"yes"| Return["return singleton"]
    Exists -->|"no"| ImportLLM["from agent import get_llm_client"]
    ImportLLM --> MongoURL["normalize_mongodb_url(settings.MONGODB_URL)"]
    MongoURL --> Client["MongoClient(..., timeout kwargs)"]
    Client --> Saver["MongoDBSaver(client, db_name=settings.MONGODB_DB)"]
    Saver --> Build["build_claim_workflow(llm_client, checkpointer)"]
    Build --> Cache["store _compiled_graph"]
    Cache --> Return
```

## Workflow state helpers

`build_initial_state` chuẩn hóa mọi run mới về cùng shape. `build_workflow_response` là boundary response cho UI/API, không expose toàn bộ internal fields.

```mermaid
flowchart LR
    Request["ClaimRequest + OCR result"] --> Initial["build_initial_state"]
    Initial --> GraphState["GraphState<br/>active_stage=completeness<br/>workflow_status=running"]
    Snapshot["LangGraph snapshot"] --> Pause["extract_pause_state"]
    Result["Graph result state"] --> Response["build_workflow_response"]
    Pause --> Response
    Response --> APIShape["run_id, claim_id, extracted_documents,<br/>agent results, final_result,<br/>current_step, status, pause flags,<br/>history, error"]
```

Pause rules:

| Snapshot condition | Response flags |
| --- | --- |
| `snapshot.next` empty | `pending=false`, `paused=false`, `pause_at=null` |
| `snapshot.next` contains `human_review` | `pending=true`, `paused=true`, `pause_at=human_review` |
| Other next node exists | `pending=false`, `paused=true`, `pause_at=<next node>` |

## OCR service logic

Service hỗ trợ:

- v1: `/api/v1/ocr/document`
- v2 phase 1: `/api/v2/ocr/classify-segment/form`
- v2 phase 2: `/api/v2/ocr/extract/form`

Default pipeline hiện tại là v2 `two_phase_gated`.

```mermaid
flowchart TD
    Prepare["prepare_ocr_result"] --> Version{"OCR_API_VERSION"}
    Version -->|"v1"| CacheV1["cache query<br/>file_hash + v1 + v1_document + v1"]
    Version -->|"v2"| CacheP1["cache query<br/>file_hash + v2 + phase1_classified + two_phase_gated"]
    CacheV1 --> Hit1{"cache hit?"}
    CacheP1 --> HitP1{"cache hit?"}
    Hit1 -->|"yes"| Reuse1["reuse OCR result<br/>save audit cache_status=reused"]
    HitP1 -->|"yes"| ReuseP1["reuse OCR result<br/>save audit cache_status=reused"]
    Hit1 -->|"no"| V1["POST OCR /api/v1/ocr/document"]
    HitP1 -->|"no"| P1["POST OCR /api/v2/ocr/classify-segment/form"]
    V1 --> Save1["save OCR audit cache_status=created"]
    P1 --> NormalizeP1["_normalize_ocr_v2_result<br/>ocr_stage=phase1_classified"]
    NormalizeP1 --> SaveP1["save OCR audit cache_status=created"]

    Phase2["prepare_ocr_phase2_result"] --> CacheP2["cache query<br/>file_hash + v2 + phase2_extracted + two_phase_gated"]
    CacheP2 --> HitP2{"cache hit?"}
    HitP2 -->|"yes"| ReuseP2["reuse phase 2 result"]
    HitP2 -->|"no"| P2["POST OCR /api/v2/ocr/extract/form<br/>documents + extract_all_fields"]
    P2 --> NormalizeP2["_normalize_ocr_v2_result<br/>ocr_stage=phase2_extracted"]
    NormalizeP2 --> SaveP2["save OCR audit"]
```

## OCR cache/audit document

```mermaid
erDiagram
    DOCUMENTS {
        string run_id
        string claim_id
        string policy_number
        string file_path
        string file_hash
        string ocr_version
        string ocr_stage
        string ocr_pipeline
        string cache_status
        string source_document_id
        object ocr_result
        datetime created_at
    }
```

Cache lookup chỉ reuse documents có `cache_status` absent hoặc `created`; mỗi reuse vẫn insert một audit row mới với `cache_status="reused"` và `source_document_id`.

## Upload file policy

`file_policy.py` bảo vệ hai boundary:

- Metadata upload: extension và MIME.
- Pairing giữa extension và MIME.
- Path resolution: path phải nằm trong `UPLOADS_DIR`, kể cả absolute path.

```mermaid
flowchart TD
    Input["filename/content_type/path"] --> Metadata["validate_upload_metadata"]
    Metadata --> Ext{"extension in .pdf/.png/.jpg/.jpeg?"}
    Metadata --> Mime{"MIME in application/pdf/image/png/image/jpeg?"}
    Ext -->|"no"| RejectExt["HTTP 415 unsupported extension"]
    Mime -->|"no"| RejectMime["HTTP 415 unsupported MIME"]
    Ext -->|"yes"| Pair{"extension matches MIME?"}
    Mime -->|"yes"| Pair
    Pair -->|"no"| RejectPair["HTTP 415 extension/MIME mismatch"]
    Pair -->|"yes"| SafeName["safe_upload_filename"]
    Path["input_file"] --> Resolve["resolve_upload_path"]
    Resolve --> Contained{"resolved path inside UPLOADS_DIR?"}
    Contained -->|"no"| RejectPath["HTTP 400 path outside upload dir"]
    Contained -->|"yes"| OK["safe path"]
```

## Config lifecycle

`Settings` đọc `.env`, parse bool-like string, validate OCR version/pipeline, và `validate_startup_config` chặn production thiếu key hoặc CORS wildcard.

```mermaid
flowchart TD
    Env[".env / environment"] --> Settings["Settings()"]
    Settings --> Bool["parse_bool_like_env<br/>release/prod=false<br/>debug/dev=true"]
    Settings --> OCRVersion["normalize OCR_API_VERSION<br/>v1 or v2"]
    Settings --> Pipeline{"OCR v2 pipeline == two_phase_gated?"}
    Pipeline -->|"no"| ConfigError["ValueError"]
    Pipeline -->|"yes"| Startup["validate_startup_config"]
    Startup --> Debug{"DEBUG?"}
    Debug -->|"true"| AllowDev["missing keys tolerated<br/>CORS '*' allowed"]
    Debug -->|"false"| Required{"GEMINI_API_KEY<br/>MONGODB_URL<br/>OCR_SERVICE_URL present?"}
    Required -->|"no"| RuntimeError["RuntimeError missing env"]
    Required -->|"yes"| CORS{"ALLOWED_ORIGINS contains '*'?"}
    CORS -->|"yes"| RuntimeError2["RuntimeError wildcard CORS"]
    CORS -->|"no"| Ready["app startup ok"]
```
