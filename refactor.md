# Refactor Architecture Plan

Roadmap này ghi lại kế hoạch refactor kiến trúc cho Agent Service và OCR Service dựa trên 5 issue đã được đánh giá. Đây là tài liệu định hướng thực thi, không mô tả thay đổi đã hoàn tất.

## Baseline

- Agent Service đã có explicit workflow state: `active_stage`, `review_stage`, `workflow_status`, và `ocr_stage`.
- Test baseline gần nhất trong `src/agent-service/plan.md`: `139 passed`.
- Chưa có `CONTEXT.md` hoặc ADR trong repo. Domain vocabulary tạm dùng từ README/docs hiện tại: insurance claim workflow, OCR phase 1/2, Completeness Agent, Quality Agent, Decision Agent, verifier gate, human review, GraphState.
- Khi thực hiện refactor code, phải chạy GitNexus impact analysis trước khi sửa function, class, method, hoặc symbol theo hướng dẫn trong `AGENTS.md`.

## Priority Order

1. Workflow Routing Policy Module - Critical
2. OCR Pipeline Module - Critical
3. Human Review Application Module - Scheduled
4. OCR Service V2 Operation Module - Scheduled
5. Agent Node Specification Module - Scheduled

## Task Tracking Board

Status convention:

- `[ ]` Todo.
- `[~]` In progress.
- `[x]` Done.
- `[!]` Blocked.

Tracking rules:

- Mỗi task code refactor phải bắt đầu bằng GitNexus impact analysis cho symbol liên quan.
- Mỗi milestone phải chạy baseline test trước khi sửa và verification test sau khi sửa.
- Không đổi API/wire contract nếu task không ghi rõ migration.
- Khi một task tạo Seam mới, task đó phải có ít nhất production Adapter và test/fake Adapter.
- Ưu tiên deep module hơn generic framework: policy nên tập trung domain decisions hiện có, chưa tạo runtime plugin/config phức tạp nếu chưa có nhu cầu thật.

### R0 - Research and Baseline

- [ ] R0-01 - Chốt source of truth cho domain vocabulary.
  - Output: tạo hoặc cập nhật `CONTEXT.md` nếu team muốn vocabulary bền vững.
  - Acceptance: các thuật ngữ claim workflow, OCR phase 1/2, verifier gate, human review được định nghĩa một lần.
  - Dependency: none.
- [ ] R0-02 - Chạy baseline verification trước refactor.
  - Commands:
    - `python -m ruff check src/agent-service`
    - `python -m pytest src/agent-service/tests -q`
    - `STRICT_SKILL_LOADING=true python -m pytest src/agent-service/tests -q`
  - Acceptance: kết quả được ghi lại trong `refactor.md` hoặc commit notes trước khi sửa code.
  - Dependency: none.
- [ ] R0-03 - Ghi current blast-radius notes cho 2 Critical milestones.
  - Commands:
    - `npx gitnexus impact route_after_completeness --direction upstream`
    - `npx gitnexus impact prepare_ocr_result --direction upstream`
    - `npx gitnexus impact run_ocr_extraction --direction upstream`
  - Acceptance: biết direct callers, affected processes, và risk level trước khi sửa routing/OCR.
  - Dependency: R0-02.

### WRP - Workflow Routing Policy Module

- [x] WRP-01 - Research current routing responsibilities.
  - Files: `graphs/routing.py`, `services/workflow_state.py`, `graphs/agent_review.py`, `graphs/human_review.py`.
  - Acceptance: liệt kê được toàn bộ decision sources: agent result, edited result, human decision, OCR stage, review stage, legacy current step.
  - Dependency: R0-03.
- [x] WRP-02 - Bổ sung baseline routing tests trước khi refactor.
  - Files: `tests/test_routing.py`, nếu cần thêm `tests/test_workflow_policy.py`.
  - Cases: completeness accept v1/v2, quality accept/reject/edit, auto-reviewed verifier pass, verifier escalation, final human approve/reject, legacy checkpoint fallback.
  - Acceptance: tests fail only nếu behavior hiện tại bị đổi ngoài ý muốn.
  - Dependency: WRP-01.
- [x] WRP-03 - Tạo Workflow Routing Policy Module.
  - Suggested file: `src/agent-service/graphs/workflow_policy.py`.
  - Interface: functions hoặc class method nhận `GraphState` và trả graph node name, normalized decision, hoặc stage metadata.
  - Acceptance: module mới sở hữu decision extraction, human decision normalization, review-stage resolution, OCR-stage routing, và stage/result-key mapping.
  - Dependency: WRP-02.
- [x] WRP-04 - Chuyển `graphs/routing.py` thành Adapter mỏng.
  - Acceptance: public routing function names giữ nguyên để `claim_workflow.py` không đổi nhiều; mỗi function chủ yếu gọi policy.
  - Dependency: WRP-03.
- [x] WRP-05 - Đồng bộ `AgentReviewNode` với policy.
  - Acceptance: stage/result-key selection trong verifier gate luôn lấy từ policy, không tự suy luận bằng `if stage == completeness else quality`.
  - Customize target: thêm stage mới chỉ cần bổ sung stage metadata/policy trước, không sửa verifier gate để biết thêm result key mới.
  - Dependency: WRP-03.
- [x] WRP-06 - Verification cho milestone.
  - Commands:
    - `python -m pytest src/agent-service/tests/test_routing.py -q`
    - `python -m pytest src/agent-service/tests/test_workflow_state.py -q`
    - `python -m pytest src/agent-service/tests/test_agent_review.py -q`
    - `python -m ruff check src/agent-service`
  - Acceptance: toàn bộ commands pass, API route names và response shape không đổi.
  - Dependency: WRP-04, WRP-05.
  - Evidence:
    - `python -m pytest src/agent-service/tests/test_routing.py -q`: 53 passed.
    - `python -m pytest src/agent-service/tests/test_agent_review.py -q`: 12 passed.
    - `python -m pytest src/agent-service/tests/test_workflow_state.py -q`: 8 passed.
    - `python -m ruff check src/agent-service`: passed.
    - `python -m pytest src/agent-service/tests -q`: 152 passed.
    - `STRICT_SKILL_LOADING=true python -m pytest src/agent-service/tests -q`: 152 passed.

### OCRP - OCR Pipeline Module

- [x] OCRP-01 - Research current OCR orchestration and cache contract.
  - Files: `services/ocr_service.py`, `graphs/ocr_extraction.py`, `tests/test_ocr_service.py`, `tests/test_ocr_extraction.py`.
  - Acceptance: map rõ phase 1 classify, phase 2 extract, cache query, audit insert, normalize result, file path policy.
  - Dependency: R0-03.
- [x] OCRP-02 - Bổ sung baseline OCR tests trước khi refactor.
  - Cases: v1 document, v2 classify, v2 extract, cache reused/created, phase 2 missing phase1 documents returns quality reject.
  - Acceptance: tests mô tả behavior hiện tại qua public helper hoặc pipeline Interface.
  - Dependency: OCRP-01.
- [x] OCRP-03 - Tạo OCR Pipeline Module.
  - Suggested file: `src/agent-service/services/ocr_pipeline.py`.
  - Interface: `prepare_initial_ocr(...)` và `prepare_phase2_ocr(...)` hoặc class tương đương.
  - Acceptance: cache lookup, audit save, selected version/stage/pipeline, và result normalization nằm trong pipeline.
  - Dependency: OCRP-02.
- [x] OCRP-04 - Tạo OCR Service Adapter.
  - Suggested role: Adapter sở hữu HTTP multipart calls tới OCR Service.
  - Acceptance: pipeline không còn tự build HTTP endpoint/form payload; tests có fake Adapter không cần network.
  - Dependency: OCRP-03.
- [x] OCRP-05 - Cập nhật graph OCR extraction node.
  - File: `graphs/ocr_extraction.py`.
  - Acceptance: node gọi pipeline Interface và không còn biết chi tiết OCR HTTP/cache; vẫn giữ error-to-quality-reject behavior.
  - Dependency: OCRP-04.
- [x] OCRP-06 - Verification cho milestone.
  - Commands:
    - `python -m pytest src/agent-service/tests/test_ocr_service.py -q`
    - `python -m pytest src/agent-service/tests/test_ocr_extraction.py -q`
    - `python -m pytest src/agent-service/tests/test_routing.py -q`
    - `STRICT_SKILL_LOADING=true python -m pytest src/agent-service/tests -q`
  - Acceptance: commands pass; `GraphState.extracted_documents` shape không đổi.
  - Dependency: OCRP-05.
  - Evidence:
    - Baseline `python -m pytest src/agent-service/tests/test_ocr_service.py -q`: 8 passed.
    - Baseline `python -m pytest src/agent-service/tests/test_ocr_extraction.py -q`: 2 passed.
    - `python -m pytest src/agent-service/tests/test_ocr_service.py -q`: 10 passed.
    - `python -m pytest src/agent-service/tests/test_ocr_extraction.py -q`: 2 passed.
    - `python -m pytest src/agent-service/tests/test_routing.py -q`: 53 passed.
    - `python -m ruff check src/agent-service`: passed.
    - `STRICT_SKILL_LOADING=true python -m pytest src/agent-service/tests -q`: 154 passed.
- [x] OCRP-07 - Giảm primitive contract trong OCR Pipeline.
  - Files: `services/ocr_pipeline.py`, `tests/test_ocr_service.py`.
  - Acceptance: pipeline orchestration dùng context/spec/cache identity rõ nghĩa thay vì truyền nhiều string rời trong internals; cache identity encode OCR version/stage/pipeline/model/document codes/extract settings và phase 1 document fingerprint cho phase 2.
  - Dependency: OCRP-06.
- [x] OCRP-08 - Thu hẹp OCR Service compatibility facade.
  - Files: `services/ocr_service.py`, `tests/test_ocr_service.py`.
  - Acceptance: façade cũ chỉ giữ public wrappers cần cho caller hiện tại; tests mới không patch `settings`, `requests`, hoặc private helper thông qua `services.ocr_service`.
  - Dependency: OCRP-07.
- [x] OCRP-09 - Verification cho OCR hardening.
  - Commands:
    - `python -m pytest src/agent-service/tests/test_ocr_service.py src/agent-service/tests/test_ocr_extraction.py src/agent-service/tests/test_routing.py -q`
    - `python -m ruff check src/agent-service`
    - `STRICT_SKILL_LOADING=true python -m pytest src/agent-service/tests -q`
    - `npx gitnexus detect-changes`
  - Acceptance: commands pass; `GraphState.extracted_documents` shape và workflow public API không đổi.
  - Dependency: OCRP-08.
  - Evidence:
    - Baseline `python -m pytest src/agent-service/tests/test_ocr_service.py src/agent-service/tests/test_ocr_extraction.py src/agent-service/tests/test_routing.py -q`: 65 passed.
    - `python -m pytest src/agent-service/tests/test_ocr_service.py src/agent-service/tests/test_ocr_extraction.py src/agent-service/tests/test_routing.py -q`: 66 passed.
    - `python -m ruff check src/agent-service`: passed.
    - `STRICT_SKILL_LOADING=true python -m pytest src/agent-service/tests -q`: 155 passed.
    - `npx gitnexus detect-changes`: risk medium; affected flows remain OCR workflow paths (`run_workflow`, `run_workflow_stream`, `run_ocr_extraction`).

### HRA - Human Review Application Module

- [ ] HRA-01 - Research resume workflow responsibilities.
  - Files: `api/workflows.py`, `services/workflow_state.py`, `graphs/human_review.py`, `tests/test_human_review.py`.
  - Acceptance: phân tách rõ route Adapter, graph checkpoint mechanics, command validation, edited-result wiring, response building.
  - Dependency: WRP-06 recommended.
- [ ] HRA-02 - Bổ sung tests cho human review application behavior.
  - Cases: approve/reject/edit ở completeness, quality, final; missing run returns 404; timeout returns standardized 504.
  - Acceptance: behavior được test không cần Streamlit UI.
  - Dependency: HRA-01.
- [ ] HRA-03 - Tạo Human Review Application Module.
  - Suggested file: `src/agent-service/services/human_review_application.py`.
  - Interface: function/class nhận `run_id`, review request/command, graph provider, và trả workflow response.
  - Acceptance: module mới sở hữu `HumanReviewResult.model_validate()`, review-stage inference, state update, graph continuation.
  - Dependency: HRA-02.
- [ ] HRA-04 - Làm mỏng `resume_workflow`.
  - File: `api/workflows.py`.
  - Acceptance: route chỉ gọi application module và map HTTP errors; route không còn set `edited_agent_1_result`/`edited_agent_2_result` trực tiếp.
  - Dependency: HRA-03.
- [ ] HRA-05 - Verification cho milestone.
  - Commands:
    - `python -m pytest src/agent-service/tests/test_human_review.py -q`
    - `python -m pytest src/agent-service/tests/test_api_schemas.py -q`
    - `python -m pytest src/agent-service/tests/test_api_status.py -q`
    - `python -m pytest src/agent-service/tests/test_workflow_state.py -q`
  - Acceptance: commands pass; `/workflows/resume/{run_id}` request/response contract không đổi.
  - Dependency: HRA-04.

### V2O - OCR Service V2 Operation Module

- [ ] V2O-01 - Research OCR v2 route duplication.
  - Files: `src/ocr-service/api/routes.py`, `src/ocr-service/core/engine/v2.py`, `src/ocr-service/tests/test_v2_routes.py`.
  - Acceptance: liệt kê repeated concerns: file loading, schema resolution, model params, response validation, JSON/form divergence.
  - Dependency: OCRP-06 recommended.
- [ ] V2O-02 - Bổ sung operation-level tests.
  - Suggested test file: `src/ocr-service/tests/test_v2_operations.py`.
  - Cases: prefilter, classify-segment, extract, extract-full; JSON/form payloads resolve to same operation behavior.
  - Acceptance: operation behavior được test ngoài route.
  - Dependency: V2O-01.
- [ ] V2O-03 - Tạo OCR v2 Operation Module.
  - Suggested file: `src/ocr-service/core/operations/v2.py`.
  - Acceptance: module sở hữu schema resolution, file content resolution policy, model parameter packaging, và response validation.
  - Dependency: V2O-02.
- [ ] V2O-04 - Làm mỏng JSON/form routes.
  - File: `src/ocr-service/api/routes.py`.
  - Acceptance: endpoint paths và response models giữ nguyên; routes chỉ parse request/form và gọi operation module.
  - Dependency: V2O-03.
- [ ] V2O-05 - Verification cho milestone.
  - Commands:
    - `python -m pytest src/ocr-service/tests/test_v2_routes.py -q`
    - `python -m pytest src/ocr-service/tests/test_v2_api_contract.py -q`
    - `python -m pytest src/ocr-service/tests/test_api_utils.py -q`
    - `python -m pytest src/ocr-service/tests -q`
  - Acceptance: commands pass; OCR v2 public contract không đổi.
  - Dependency: V2O-04.

### ANS - Agent Node Specification Module

- [ ] ANS-01 - Research agent lifecycle responsibilities.
  - Files: `agents/factory.py`, `agents/prompt_builders.py`, `agents/output_parsing.py`, `agents/audit.py`, `tools/skill_loader.py`.
  - Acceptance: map rõ concern nào đã tách, concern nào vẫn còn trong factory/spec convention.
  - Dependency: WRP-06 and OCRP-06 recommended.
- [ ] ANS-02 - Bổ sung tests cho role-level behavior.
  - Cases: Completeness, Quality, Decision, Verifier dùng đúng prompt builder, schema, output key, active/review stage update, audit behavior.
  - Acceptance: tests không cần gọi LLM thật; dùng fake LLM Adapter.
  - Dependency: ANS-01.
- [ ] ANS-03 - Tạo Agent Node Specification Module.
  - Suggested file: `src/agent-service/agents/node_specs.py`.
  - Acceptance: role spec tập trung skill name, prompt name, output key, display name, schema, and stage policy.
  - Dependency: ANS-02.
- [ ] ANS-04 - Làm mỏng factory.
  - File: `agents/factory.py`.
  - Acceptance: factory chỉ assemble node từ spec và shared runtime; không còn rải string convention ở từng subclass.
  - Dependency: ANS-03.
- [ ] ANS-05 - Verification cho milestone.
  - Commands:
    - `python -m pytest src/agent-service/tests/test_agent_prompt_builders.py -q`
    - `python -m pytest src/agent-service/tests/test_agent_output_parsing.py -q`
    - `python -m pytest src/agent-service/tests/test_agent_audit.py -q`
    - `python -m pytest src/agent-service/tests/test_agent_review.py -q`
    - `STRICT_SKILL_LOADING=true python -m pytest src/agent-service/tests -q`
  - Acceptance: commands pass; output keys and `GraphState` shape không đổi.
  - Dependency: ANS-04.

## 1. Workflow Routing Policy Module

### Current Problem

Routing của insurance claim workflow hiện nằm rải ở nhiều nơi và caller/test phải biết quá nhiều chi tiết của `GraphState`: `agent_1_result`, `agent_2_result`, edited results, `review_stage`, `current_step`, `ocr_stage`, `is_auto_reviewed`, và literal decision values.

Module hiện tại còn shallow vì Interface gần như phơi bày toàn bộ Implementation. Khi thay đổi workflow, khả năng phải sửa nhiều file và nhiều test là cao.

### Risk Assessment

- Pain x Spread: `3 x 3 = 9`.
- Priority: Critical.
- Decay risks:
  - Change Propagation: thay đổi transition có thể lan sang graph routing, workflow state, agent review, status response, UI timeline.
  - Knowledge Duplication: stage inference và decision mapping xuất hiện ở nhiều module.
  - Domain Model Distortion: nghiệp vụ "hồ sơ đang ở giai đoạn nào" bị biểu diễn bằng nhiều key kỹ thuật thay vì một policy rõ ràng.

### Target Architecture

Tạo một Workflow Routing Policy Module chịu trách nhiệm quyết định transition của insurance claim workflow.

Interface mục tiêu nên xoay quanh các câu hỏi nghiệp vụ:

- Sau Completeness Agent thì đi đâu?
- Sau Quality Agent thì đi đâu?
- Sau verifier gate thì tiếp tục tự động hay cần human review?
- Sau human review thì quay lại stage nào hoặc kết thúc?
- OCR phase 1 đã đủ để vào Quality Agent chưa, hay cần OCR phase 2?

Implementation bên trong mới được biết chi tiết `GraphState`, legacy `current_step` fallback, edited results, và auto-review flags.

Policy này cũng nên sở hữu stage metadata tối thiểu để workflow scale được khi thêm agent/stage mới:

- `result_key`: state key chứa kết quả stage, ví dụ `agent_1_result`, `agent_2_result`.
- `edited_result_key`: state key chứa kết quả human edit nếu stage cho phép edit.
- `review_stage`: stage nghiệp vụ đang được verifier hoặc human review.
- `next_after_accept`: graph node tiếp theo khi stage accept.
- `next_after_auto_review`: graph node tiếp theo khi verifier gate pass.
- `next_after_human_edit`: graph node cần chạy lại khi human chọn edit.
- `requires_phase2_ocr`: chỉ dùng cho completeness/OCR phase 1 nếu cần phân nhánh phase 2.

Mục tiêu customize: nếu sau này thêm `coverage_check`, `fraud_check`, hoặc `payment_check`, verifier gate và human review không cần biết key mới bằng `if/else` riêng. Implementer chỉ thêm stage metadata và tests cho transition mới. Không tạo runtime plugin system trong milestone đầu; policy nên là Python module đơn giản, explicit, dễ đọc.

### Implementation Steps

1. Chạy GitNexus impact analysis cho các symbol sẽ sửa trong `graphs/routing.py`, `services/workflow_state.py`, và `graphs/agent_review.py`.
2. Thêm baseline tests cho những transition quan trọng nếu chưa có:
   - Completeness accept với `ocr_stage=phase1_classified` route sang OCR extraction.
   - Completeness accept với `ocr_stage=v1_document` route sang Quality Agent.
   - Completeness/Quality `accept_with_edit` route sang verifier gate.
   - Verifier auto-approved route sang stage tiếp theo.
   - Verifier escalation route sang human review.
   - Final human approve/reject kết thúc workflow.
3. Tạo module policy mới, ưu tiên đặt gần graph layer để không làm API phụ thuộc vào graph internals nhiều hơn.
4. Di chuyển decision extraction, review-stage resolution, human decision normalization, và OCR-stage routing vào policy.
5. Giữ public behavior và route names hiện tại. Không đổi API response shape.
6. Giữ compatibility fallback cho checkpoint cũ còn dùng `current_step`.
7. Sau khi tests qua policy đầy đủ, giảm logic trong `graphs/routing.py` xuống còn adapter mỏng gọi policy.

### Verification

- `python -m pytest src/agent-service/tests/test_routing.py -q`
- `python -m pytest src/agent-service/tests/test_workflow_state.py -q`
- `python -m pytest src/agent-service/tests/test_agent_review.py -q`
- `python -m ruff check src/agent-service`
- `STRICT_SKILL_LOADING=true python -m pytest src/agent-service/tests -q`

### Stop Condition

Milestone hoàn tất khi toàn bộ transition rules chính được test qua một Interface policy duy nhất, `graphs/routing.py` không còn chứa nhiều rule nghiệp vụ rải rác, và API behavior/status response không đổi.

## 2. OCR Pipeline Module

### Current Problem

Agent Service gọi OCR qua các helper trả về dict lỏng. Caller phải biết `ocr_version`, `ocr_pipeline`, `ocr_stage`, `documents`, cache semantics, HTTP form fields, audit save, và quy tắc làm sạch classification data trước phase 2.

Seam với OCR Service là thật, nhưng Adapter shape chưa rõ. Điều này làm graph node, cache logic, HTTP client logic, và audit logic dính vào nhau.

### Risk Assessment

- Pain x Spread: `3 x 3 = 9`.
- Priority: Critical.
- Decay risks:
  - Change Propagation: thay đổi OCR phase, cache key, hoặc response shape có thể ảnh hưởng graph, service helper, tests, và OCR Service contract.
  - Dependency Disorder: workflow domain đang biết chi tiết HTTP/multipart của OCR Service.
  - Cognitive Overload: cần hiểu nhiều field dict và stage constants để sửa một luồng OCR.

### Target Architecture

Tạo OCR Pipeline Module sở hữu toàn bộ orchestration OCR cho insurance claim workflow.

Interface mục tiêu:

- Classify claim document cho OCR phase 1.
- Extract classified documents cho OCR phase 2.
- Reuse OCR result từ cache theo file hash/version/stage/pipeline.
- Audit OCR result sau mỗi lần create/reuse.

OCR HTTP call nên nằm sau `OcrServiceAdapter`. Tests có thể dùng fake Adapter để graph không phụ thuộc network hoặc OCR Service thật.

### Implementation Steps

1. Chạy GitNexus impact analysis cho `prepare_ocr_result`, `prepare_ocr_phase2_result`, `run_ocr_document`, `run_ocr_v2_extract`, và `run_ocr_extraction`.
2. Ghi baseline tests hiện có cho OCR cache, phase 1, phase 2, và graph OCR extraction.
3. Tạo một data shape nội bộ cho OCR pipeline output, nhưng vẫn serialize về dict hiện tại khi đưa vào `GraphState`.
4. Tách OCR HTTP Adapter khỏi cache/audit orchestration.
5. Tách logic normalize OCR v2 result và build cache query vào pipeline internals.
6. Cập nhật `graphs/ocr_extraction.py` để gọi pipeline Interface thay vì biết chi tiết phase 1 document cleanup.
7. Giữ nguyên API response và `GraphState.extracted_documents` shape trong milestone đầu để tránh migration lớn.

### Verification

- `python -m pytest src/agent-service/tests/test_ocr_service.py -q`
- `python -m pytest src/agent-service/tests/test_ocr_extraction.py -q`
- `python -m pytest src/agent-service/tests/test_routing.py -q`
- Với thay đổi OCR Service contract: `python -m pytest src/ocr-service/tests -q`
- Full check sau milestone: `STRICT_SKILL_LOADING=true python -m pytest src/agent-service/tests -q`

### Stop Condition

Milestone hoàn tất khi graph và API không còn biết chi tiết HTTP/multipart/cache query của OCR, tests có thể dùng fake OCR Adapter, và OCR v1/v2 branching nằm tập trung trong OCR Pipeline Module.

## 3. Human Review Application Module

### Current Problem

`resume_workflow` đang xử lý quá nhiều trách nhiệm: load checkpoint, infer review stage, validate `HumanReviewResult`, đặt edited result vào đúng state key, update graph state với `as_node="human_review"`, tiếp tục graph, rồi build response.

FastAPI route hiện là Adapter nhưng đang mang nhiều Implementation knowledge của graph.

### Risk Assessment

- Pain x Spread: `2 x 3 = 6`.
- Priority: Scheduled.
- Decay risks:
  - Change Propagation: thay đổi human review behavior ảnh hưởng route, graph state, routing, tests, và UI.
  - Domain Model Distortion: hành động nghiệp vụ approve/reject/edit bị trộn với checkpoint mechanics.
  - Knowledge Duplication: review stage inference xuất hiện trong nhiều nơi.

### Target Architecture

Tạo Human Review Application Module tại Seam giữa API và LangGraph.

Interface mục tiêu:

- Apply human review decision cho một `run_id`.
- Validate review command.
- Ghi edited result đúng stage.
- Continue workflow và trả workflow response chuẩn.

FastAPI chỉ nhận request, gọi module, và map lỗi HTTP.

### Implementation Steps

1. Chạy GitNexus impact analysis cho `resume_workflow`, `determine_review_stage`, và `HumanReviewNode.run`.
2. Thêm hoặc xác nhận tests cho approve/reject/edit ở completeness, quality, final.
3. Tạo command object hoặc dict rõ ràng cho human review request nội bộ.
4. Di chuyển review-stage inference và edited-result wiring khỏi route.
5. Đảm bảo module mới vẫn dùng `HumanReviewResult.model_validate()` trước khi inject vào graph state.
6. Giữ endpoint path và request/response schema hiện tại.
7. Rút `api/workflows.py::resume_workflow` xuống còn route Adapter mỏng.

### Verification

- `python -m pytest src/agent-service/tests/test_human_review.py -q`
- `python -m pytest src/agent-service/tests/test_api_schemas.py -q`
- `python -m pytest src/agent-service/tests/test_api_status.py -q`
- Add focused tests cho application module nếu module mới có logic đáng kể.

### Stop Condition

Milestone hoàn tất khi approve/reject/edit behavior được test qua Human Review Application Module, route không còn biết state key `edited_agent_1_result`/`edited_agent_2_result`, và API contract không đổi.

## 4. OCR Service V2 Operation Module

### Current Problem

OCR Service v2 JSON/form routes lặp lại nhiều plumbing: file loading, schema resolution, model parameters, response validation, operation selection. Engine v2 cũng đang chứa nhiều concern: phase 1/2 orchestration, PDF slicing, model selection, parallel extraction, usage aggregation.

### Risk Assessment

- Pain x Spread: `2 x 2 = 4`.
- Priority: Scheduled.
- Decay risks:
  - Accidental Complexity: route layer mirror quá nhiều implementation parameter.
  - Knowledge Duplication: JSON và form endpoints lặp schema/model/file handling.
  - Cognitive Overload: sửa một operation phải đọc cả route và engine.

### Target Architecture

Tạo OCR Service V2 Operation Module sở hữu các operation nghiệp vụ:

- Prefilter.
- Classify-segment.
- Extract.
- Extract-full.

JSON/form routes trở thành Adapters chuyển input sang operation command. Operation Module sở hữu schema resolution, file loading policy, validation, và gọi engine.

### Implementation Steps

1. Chạy GitNexus impact analysis cho các OCR v2 route functions và `OCRServiceV2` methods sẽ sửa.
2. Xác nhận tests hiện có trong `src/ocr-service/tests` trước khi refactor.
3. Tạo shared operation layer cho v2.
4. Di chuyển schema resolution và model parameter handling vào operation layer.
5. Giữ response models và endpoint paths hiện tại.
6. Chỉ giảm route duplication sau khi operation tests cover JSON/form behavior.

### Verification

- `python -m pytest src/ocr-service/tests/test_v2_routes.py -q`
- `python -m pytest src/ocr-service/tests/test_v2_api_contract.py -q`
- `python -m pytest src/ocr-service/tests/test_api_utils.py -q`

### Stop Condition

Milestone hoàn tất khi JSON/form routes chỉ còn Adapter logic, v2 operation behavior được test ngoài HTTP route, và response contract không đổi.

## 5. Agent Node Specification Module

### Current Problem

Agent runtime hiện phụ thuộc nhiều cấu hình string: skill name, prompt name, output key, display name, schema class, active stage inference, review stage inference. `AgentFactory` còn gom nhiều concern: skill loading, prompt building, LLM invocation, output extraction, JSON parsing, schema validation, audit logging, và GraphState update.

Một phần đã được tách ra trong roadmap cũ, nhưng role-specific Interface vẫn chưa đủ sâu.

### Risk Assessment

- Pain x Spread: `2 x 2 = 4`.
- Priority: Scheduled.
- Decay risks:
  - Cognitive Overload: cần hiểu nhiều convention để thêm hoặc sửa agent.
  - Accidental Complexity: generic factory có nguy cơ trở thành mini-framework.
  - Change Propagation: thay đổi lifecycle agent có thể ảnh hưởng nhiều role cùng lúc.

### Target Architecture

Tạo Agent Node Specification Module cho từng role hoặc một spec object rõ ràng cho từng role.

Interface mục tiêu:

- Run Completeness Agent against GraphState.
- Run Quality Agent against GraphState.
- Run Decision Agent against GraphState.
- Run Verifier Agent against GraphState.

Implementation bên trong mới biết prompt builder, skill registry, output schema, audit, và state update keys.

### Implementation Steps

1. Chạy GitNexus impact analysis cho `AgentFactory.create_agent_with_skills`, role factory methods, và prompt builders liên quan.
2. Không refactor milestone này trước Workflow Routing Policy và OCR Pipeline để tránh đổi quá nhiều seams cùng lúc.
3. Tạo spec object hoặc role module nhỏ cho mỗi agent role.
4. Giữ fake LLM tests cho parsing/schema/audit behavior.
5. Loại bỏ dần string convention khỏi call sites.
6. Giữ output state keys hiện tại cho compatibility trong milestone đầu.

### Verification

- `python -m pytest src/agent-service/tests/test_agent_prompt_builders.py -q`
- `python -m pytest src/agent-service/tests/test_agent_output_parsing.py -q`
- `python -m pytest src/agent-service/tests/test_agent_audit.py -q`
- `python -m pytest src/agent-service/tests/test_agent_review.py -q`
- Full check sau milestone: `STRICT_SKILL_LOADING=true python -m pytest src/agent-service/tests -q`

### Stop Condition

Milestone hoàn tất khi thêm hoặc sửa agent role không cần truyền nhiều string convention ở call site, tests exercise behavior qua role Interface, và `AgentFactory` không còn là nơi chứa mọi lifecycle concern.

## Execution Rules

- Refactor theo thứ tự priority, không làm đồng thời nhiều Critical seams nếu không có baseline tests.
- Mỗi milestone phải có baseline verification trước và sau.
- Không đổi public API/wire contract nếu chưa có migration note riêng.
- Không thêm Seam mới nếu chỉ có một Adapter và chưa có fake/test Adapter cần thiết.
- Nếu một issue bị defer vì lý do sản phẩm hoặc deadline, ghi ADR trước khi loại khỏi roadmap dài hạn.

## Global Verification Checklist

Chạy sau mỗi milestone có thay đổi code trong Agent Service:

```bash
python -m ruff check src/agent-service
python -m pytest src/agent-service/tests -q
STRICT_SKILL_LOADING=true python -m pytest src/agent-service/tests -q
```

Chạy thêm khi milestone đụng OCR Service:

```bash
python -m pytest src/ocr-service/tests -q
```
