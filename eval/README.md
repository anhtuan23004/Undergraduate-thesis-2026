# Evaluation Toolkit

Entrypoint chính:

```bash
uv run python -m eval --help
```

Kiểm tra code eval:

```bash
uv run ruff check eval
uv run pytest eval/tests -q
```

## Chạy 100 Hồ Sơ Qua Multi-Agent

```bash
uv run python -m eval run --limit 5 --skip-existing --build-suggestions
```

Mặc định CLI sẽ:

- đọc `eval/dataset/ground_truth.json`;
- upload PDF lên `agent-service`;
- gọi `POST /api/v1/workflows/run`;
- cập nhật tiến độ từng hồ sơ vào `eval/results/history.json`;
- lưu kết quả mỗi hồ sơ thành một file riêng trong `eval/results/claims/`;
- sinh gợi ý nhãn tổng vào `eval/results/agent_suggestions.json` nếu có `--build-suggestions`;
- sinh gợi ý nhãn từng hồ sơ vào `eval/results/suggestions/<claim_id>.json`.

`history.json` là file nhìn nhanh hồ sơ nào đã xử lý:

- `pending`: có trong batch nhưng chưa chạy;
- `running`: đang xử lý;
- `completed`: chạy xong không có lỗi;
- `failed`: chạy xong nhưng lỗi API/model/workflow;
- `skipped`: bỏ qua vì đã có kết quả và dùng `--skip-existing`.

Lưu ý về upload:

`--no-upload` vẫn được chấp nhận để tương thích lệnh cũ, nhưng hiện là no-op.
`agent-service` hiện yêu cầu `input_file` nằm trong `UPLOADS_DIR`, nên eval luôn
upload PDF trước khi gọi workflow.

Kiểm tra danh sách hồ sơ mà không gọi API:

```bash
uv run python -m eval run --limit 5 --dry-run
```

## Gán Nhãn

```bash
uv run python -m eval label-ui
```

UI Streamlit đọc `ground_truth.json` và `agent_suggestions.json`, cho phép reviewer xem PDF, áp dụng gợi ý agent, chỉnh sửa và lưu nhãn thủ công.

UI không ghi đè `ground_truth.json`. Nhãn reviewer được lưu riêng tại:

```text
eval/results/reviewed_labels.json
```

File này dùng để so sánh với output agent hoặc chuyển thành ground truth cuối cùng sau khi review xong.

## Làm Sạch Ground Truth Tạm

`eval/dataset/ground_truth.json` là manifest dữ liệu, không phải nơi lưu nhãn
tham chiếu cuối cùng. Nếu file này còn metadata hoặc nhãn tạm sinh từ agent
output để smoke test metric, chạy:

```bash
uv run python -m eval clean-ground-truth
```

Lệnh này xóa metadata `fake_*` và reset các label seed tạm về `unlabeled`, nhưng
giữ nguyên danh sách claim, file path, và category.

## Sinh Nhãn Tham Chiếu Nháp Bằng LLM Lớn

Để tạo nhãn nháp cho reviewer audit, dùng:

```bash
uv run python -m eval label-reference --limit 5
```

Mặc định command dùng `gemini-3.1-pro-preview` và ghi kết quả vào:

- `eval/results/reviewed_labels.json`
- `eval/results/audit_queue.csv`

Các nhãn này phải được hiểu là `LLM-assisted audited reference labels`. Không
dùng output của multi-agent system làm ground truth.

Nếu cần cách làm nhanh hơn theo hướng LLM-judge, có thể đưa cả output
multi-agent/single-agent và PDF text evidence cho model lớn:

```bash
uv run python -m eval label-reference \
  --limit 50 \
  --include-agent-results \
  --multi-results eval/results/claims \
  --single-results eval/results/single_agent_claims \
  --output eval/results/reviewed_labels.json
```

Mode này ghi `label_source: llm_judge_with_agent_outputs`. Đây là nhãn tham chiếu
do LLM lớn phán xét từ tài liệu + kết quả hệ thống, không phải nhãn chuyên gia
độc lập; nên audit thủ công các case confidence thấp, `needs_review`, hoặc khi
multi-agent và single-agent bất đồng.

## Chạy Baseline Single-Agent

RQ5 cần baseline single-agent dùng cùng dữ liệu OCR và cùng model với multi-agent
khi so sánh. Command baseline:

```bash
uv run python -m eval run-baseline --limit 5
```

Kết quả mặc định được lưu tại:

```text
eval/results/single_agent_claims/
```

Runner mặc định dùng `--ocr-source auto`: đọc OCR cache trong MongoDB trước
theo `claim_id`/`file_hash`, ưu tiên bản `phase2_extracted`; nếu không có mới
tìm OCR snapshot trong `eval/results/ocr_cache/`. Để đảm bảo RQ5 dùng đúng cùng
OCR cache với workflow, chạy:

```bash
uv run python -m eval run-baseline --limit 50 --ocr-source mongo --require-ocr-cache
```

Baseline mặc định là một LangChain agent duy nhất có quyền gọi cùng skill tools
chính của workflow: `check-required-docs`, `validate-consistency`, `check-icd`,
`check-exclusion`, `search-medicine`, `validate-medication`, và
`aggregate-issues`. Output ghi tool trace vào `called_tools_by_agent.SingleAgent`.
Chỉ dùng `--no-tools` khi cần debug baseline one-shot cũ.

Token usage được lấy từ provider metadata nếu có. Với baseline có tool-calling,
runner cộng token metadata của từng model call trong agent loop, nên token bao
gồm các vòng gọi tool. Nếu provider không trả metadata thì mới fallback sang
ước lượng `ceil(chars / 4)` và ghi rõ `token_usage_source`.

Với multi-agent workflow, token usage chỉ chính xác cho các lần chạy mới sau khi
agent-service đã được restart với code hiện tại; các result cũ có
`token_usage_source` rỗng hoặc `token_usage = 0` không dùng được cho báo cáo chi
phí/token.

## Tính Metrics

```bash
uv run python -m eval metrics --multi-results eval/results/claims
```

Mặc định metrics so sánh agent output với ground truth chính tại:

```text
eval/dataset/ground_truth.json
```

Nếu `ground_truth.json` chưa có nhãn `final`/`reviewed`, report vẫn sinh performance/latency/token metrics nhưng accuracy/F1 sẽ chưa được tính.

`eval/results/reviewed_labels.json` chỉ là file review tạm từ UI. Nếu muốn kiểm thử report bằng file này trước khi merge nhãn vào ground truth, truyền rõ:

```bash
uv run python -m eval metrics --multi-results eval/results/claims --labels eval/results/reviewed_labels.json
```

Kết quả được lưu vào:

- `eval/results/metrics_summary.json`;
- `eval/results/claim_level_results.csv`.
- `eval/reports/rq_report.md` khi dùng output mặc định.

## Sinh Lại Suggestions Từ Kết Quả Có Sẵn

```bash
uv run python -m eval suggestions --results eval/results/claims
```

Lệnh này tạo lại:

- `eval/results/agent_suggestions.json`;
- `eval/results/suggestions/<claim_id>.json`.
