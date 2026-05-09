# Evaluation Toolkit

Entrypoint chính:

```bash
uv run python -m eval --help
```

## Chạy 100 Hồ Sơ Qua Multi-Agent

```bash
uv run python -m eval run --skip-existing --build-suggestions
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

Nếu `agent-service` chạy local và đọc được path PDF trực tiếp:

```bash
uv run python -m eval run --skip-existing --no-upload --build-suggestions
```

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

## Sinh Lại Suggestions Từ Kết Quả Có Sẵn

```bash
uv run python -m eval suggestions --results eval/results/claims
```

Lệnh này tạo lại:

- `eval/results/agent_suggestions.json`;
- `eval/results/suggestions/<claim_id>.json`.
