# Agentic AI Insurance Claims Processing System

Hệ thống xử lý hồ sơ bồi thường bảo hiểm sức khỏe thông minh bằng kiến trúc Multi-Agent (Agentic AI). Dự án này được thiết kế và triển khai trong phạm vi khóa luận tốt nghiệp, tập trung vào việc tự động hóa quy trình tiếp nhận chứng từ, số hóa tài liệu (OCR), kiểm tra tính đầy đủ của hồ sơ (Completeness Agent), thẩm định chất lượng y tế (Quality Agent) và ra quyết định (Decision Agent) với cơ chế Human-in-the-Loop (HITL) qua giao diện vận hành.

---

## 🏛️ Kiến Trúc Tổng Quan

Hệ thống được thiết kế theo mô hình Microservices phân lớp rõ ràng, đảm bảo khả năng mở rộng và kiểm thử độc lập:

```mermaid
flowchart LR
    UI["Streamlit UI / Client<br/>:8501"] -->|"Upload, Stream, Resume"| AgentAPI["Agent Service<br/>FastAPI :8003"]

    AgentAPI --> Graph["LangGraph Workflow"]
    Graph --> Completeness["Completeness Agent"]
    Graph --> OCRPhase2["OCR Phase 2"]
    Graph --> Quality["Quality Agent"]
    Graph --> Review["Agent Review + Verifier"]
    Graph --> Human["Human Review Interrupt"]
    Graph --> Decision["Decision Agent"]

    AgentAPI --> OCR["OCR Service<br/>FastAPI :8001 / :8091"]
    OCR --> Gemini["Google Gemini API"]

    AgentAPI --> Mongo["MongoDB<br/>checkpoints, cache, audit"]
    AgentAPI --> Redis["Redis"]
    AgentAPI -. optional .-> Langfuse["Langfuse :3000"]
```

---

## 💻 Yêu Cầu Hệ Thống & Tiền Đề

Để hệ thống hoạt động ổn định trong môi trường thực nghiệm và phát triển, thiết bị của bạn cần đáp ứng:

### 1. Phần cứng khuyến nghị
- **RAM**: Tối thiểu 8 GB (Khuyên dùng 16 GB nếu chạy toàn bộ hạ tầng gồm cả Langfuse, ClickHouse, PostgreSQL, MinIO, MongoDB, Redis).
- **Disk**: Dung lượng trống tối thiểu 10 GB cho Docker Images và dữ liệu MongoDB.

### 2. Phần mềm yêu cầu
- **Docker & Docker Compose**: **Phiên bản v2.20.0+** (Bắt buộc, do cấu hình sử dụng tính năng `include` để gộp nhiều file Compose).
- **Python**: Phiên bản **3.11** hoặc **3.12** (Nếu chạy cục bộ không qua Docker).
- **uv (Astral)**: Công cụ quản lý gói và môi trường Python siêu nhanh (Thay thế cho `pip`).
  - *Cài đặt trên macOS/Linux*: `curl -LsSf https://astral.sh/uv/install.sh | sh` hoặc `brew install uv`.
  - *Cài đặt trên Windows (PowerShell)*: `irm https://astral.sh/uv/install.ps1 | iex`.
- **API Key & Token**:
  - **Google Gemini API Key**: Lấy từ [Google AI Studio](https://aistudio.google.com/).
  - **Hugging Face Access Token** (Tùy chọn): Cần thiết nếu muốn ingest dữ liệu thuốc và chạy mô hình Embedding tiếng Việt cục bộ.

---

## ⚙️ Cấu Hình File Môi Trường (`.env`)

Trước khi khởi chạy, bạn cần tạo file `.env` ở thư mục gốc của dự án bằng cách copy từ file mẫu:

```bash
cp .env.example .env
```

> [!IMPORTANT]
> Cần phân biệt rõ cấu hình khi chạy bằng **Docker Compose** và chạy **Cục bộ (Local/Hybrid)**. Dưới đây là các cấu hình quan trọng nhất:

| Tên biến môi trường | Giá trị khi chạy Docker Compose | Giá trị khi chạy Local / Hybrid | Ý nghĩa |
| :--- | :--- | :--- | :--- |
| `GEMINI_API_KEY` | `AIzaSy...` (Điền key của bạn) | `AIzaSy...` (Điền key của bạn) | Key API của Google Gemini để chạy OCR và Agents. |
| `OCR_SERVICE_URL` | `http://ocr-service:8000` | `http://localhost:8091` | Địa chỉ endpoint gọi sang dịch vụ OCR Service. |
| `MONGODB_URL` | `mongodb://admin:admin123@mongodb:27017/...` | `mongodb://admin:admin123@localhost:27017/...` | URL kết nối cơ sở dữ liệu MongoDB. |
| `REDIS_URL` | `redis://redis:6379/0` | `redis://localhost:6379/0` | URL kết nối Redis. |
| `STRICT_SKILL_LOADING` | `false` | `false` (Đặt `true` khi test) | Nếu bật `true`, hệ thống sẽ crash ngay lập tức nếu bất kỳ Agent Tool/Skill nào lỗi khi tải. |
| `LANGFUSE_ENABLED` | `false` (Bật `true` để giám sát) | `false` (Bật `true` để giám sát) | Kích hoạt gửi logs giám sát LLM/Agent về Langfuse. |

---

## 🚀 Các Phương Án Triển Khai & Khởi Chạy

### Phương án A: Khởi chạy toàn bộ hệ thống bằng Docker Compose (Khuyên dùng)

Đây là cách nhanh nhất để khởi động toàn bộ ứng dụng và các dịch vụ bổ trợ mà không cần cài đặt Python hay môi trường ảo cục bộ.

#### 1. Khởi động các container:
```bash
docker compose up -d --build
```

#### 2. Kiểm tra trạng thái các container:
```bash
docker compose ps
```

#### 3. Các cổng dịch vụ mặc định:
- **Streamlit Web UI**: [http://localhost:8501](http://localhost:8501)
- **Agent Service (FastAPI API)**: [http://localhost:8003/docs](http://localhost:8003/docs) (Cổng trong container là 8000)
- **OCR Service (FastAPI API)**: [http://localhost:8001/docs](http://localhost:8001/docs) (Cổng trong container là 8000)
- **Mongo Express (Web quản trị MongoDB)**: [http://localhost:8081](http://localhost:8081)
- **Langfuse Dashboard** (Giám sát LLM/Agent): [http://localhost:3000](http://localhost:3000)

#### 4. Xem logs của một service:
```bash
docker compose logs -f agent-service
# Hoặc xem logs ocr-service
docker compose logs -f ocr-service
```

---

### Phương án B: Khởi chạy Cục bộ / Lai (Hybrid Local Development)

Cách này phù hợp nhất cho quá trình lập trình, debug, sửa đổi code mà không cần build lại Docker image mỗi lần thay đổi. Ta sẽ chạy MongoDB & Redis bằng Docker, còn các Python services chạy trực tiếp bằng `uv` trên máy ảo cục bộ.

#### Bước 1: Khởi động cơ sở dữ liệu nền tảng bằng Docker
Chỉ khởi động MongoDB và Redis để làm backend lưu trữ:
```bash
docker compose up -d mongodb redis
```

#### Bước 2: Cài đặt và đồng bộ hóa môi trường Python ảo
Sử dụng `uv` để tạo virtual environment và cài đặt tất cả các thư viện định nghĩa trong `pyproject.toml` (bao gồm cả dev và eval tools):
```bash
uv sync --all-extras
```

#### Bước 3: Khởi chạy OCR Service cục bộ
Sử dụng script tiện ích hoặc chạy lệnh trực tiếp từ thư mục dịch vụ:
- **Cách nhanh nhất**:
  ```bash
  chmod +x ocr.sh
  ./ocr.sh
  ```
- **Cách thủ công**:
  ```bash
  cd src/ocr-service
  PYTHONPATH=. uv run uvicorn main:app --reload --host 0.0.0.0 --port 8091
  ```
  *(Service OCR chạy tại cổng `8091`)*

#### Bước 4: Khởi chạy Agent Service cục bộ
- **Cách nhanh nhất**:
  ```bash
  chmod +x agent.sh
  ./agent.sh
  ```
- **Cách thủ công**:
  ```bash
  cd src/agent-service
  OCR_SERVICE_URL=http://localhost:8091 uv run uvicorn main:app --reload --host 0.0.0.0 --port 8003
  ```
  *(Service Agent chạy tại cổng `8003`)*

#### Bước 5: Khởi chạy Streamlit UI cục bộ
- **Cách nhanh nhất**:
  ```bash
  chmod +x ui.sh
  ./ui.sh
  ```
- **Cách thủ công**:
  ```bash
  cd src/agent-service/interfaces/web
  uv run streamlit run app.py --server.port 8501
  ```

---

## 💾 Khởi Tạo Dữ Liệu Thuốc (Medicine Ingestion) & Vector Search

Trong quy trình thẩm định chất lượng y tế (Quality Agent), hệ thống sử dụng một công cụ tìm kiếm thuốc (Drug-Search Skill) để tra cứu thông tin hoạt chất, chỉ định thuốc từ cơ sở dữ liệu MongoDB. Cơ sở dữ liệu này chứa 5,293 loại thuốc tiếng Việt kèm theo vector embeddings 1024-chiều đã được mã hóa sẵn.

> [!NOTE]
> Để tiết kiệm tài nguyên và thời gian tải mô hình tạo embeddings từ HuggingFace (có thể mất tới hàng giờ), khuyến nghị khuyên dùng là khôi phục cơ sở dữ liệu từ file backup nén **`data/my_database.gz`** đã được cấu trúc và tính sẵn vector embeddings.

### 1. Khôi phục cơ sở dữ liệu thuốc từ file Backup (Khuyên dùng)
Đảm bảo MongoDB container đang chạy, sau đó chạy lệnh khôi phục (mongorestore):

- **Nếu dùng Docker Compose (khuyên dùng)**:
  Chạy lệnh pipe file backup vào lệnh `mongorestore` bên trong container:
  ```bash
  docker compose exec -T mongodb mongorestore --username admin --password admin123 --authenticationDatabase admin --gzip --archive < data/my_database.gz
  ```
- **Nếu chạy MongoDB cục bộ bên ngoài**:
  Nếu máy của bạn đã cài đặt sẵn công cụ `mongorestore`, hãy chạy:
  ```bash
  mongorestore --uri="mongodb://admin:admin123@localhost:27017/?authSource=admin&directConnection=true" --gzip --archive=data/my_database.gz
  ```

*Dữ liệu sẽ được tự động khôi phục vào database `document_qa`, collection `medicine`.*

### 2. Tạo Search Index trên MongoDB
Sau khi khôi phục dữ liệu thành công, hãy chạy script khởi tạo chỉ mục tìm kiếm (Vector Search và Full-text Search):

- **Nếu dùng Docker Compose**:
  ```bash
  docker compose exec -T mongodb mongosh --username admin --password admin123 --authenticationDatabase admin < infrastructure/mongodb/scripts/setup.js
  ```
- **Nếu chạy MongoDB cục bộ bên ngoài**:
  ```bash
  mongosh "mongodb://admin:admin123@localhost:27017?directConnection=true" < infrastructure/mongodb/scripts/setup.js
  ```

> [!TIP]
> **Dành cho nhà phát triển**: Nếu bạn có file dữ liệu gốc `merged_medicines.json` (không đính kèm trong Git repo) và muốn tự xây dựng lại toàn bộ vector embeddings từ đầu, bạn có thể thiết lập biến `HF_TOKEN` và chạy script:
> `export HF_TOKEN="your_token" && uv run python infrastructure/mongodb/scripts/ingest_medicines.py`

---

## 🧪 Kiểm Thử Hệ Thống (Testing & Verification)

Hệ thống có bộ test suite hoàn chỉnh bao gồm các Unit test, Integration test và API Contract test.

### 1. Chạy tất cả bài kiểm thử
```bash
# Kiểm thử toàn bộ dự án
uv run pytest

# Hoặc chạy kiểm thử riêng lẻ từng service
uv run pytest src/agent-service/tests
uv run pytest src/ocr-service/tests
```

### 2. Chạy kiểm thử chế độ nghiêm ngặt (Strict Skill Testing)
Đảm bảo tất cả các file cấu hình kỹ năng (`SKILL.md`) và khai báo tool của Agent được kiểm định nghiêm ngặt:
```bash
STRICT_SKILL_LOADING=true uv run pytest src/agent-service/tests
```

### 3. Kiểm tra định dạng code & Linting
```bash
# Chạy Ruff linter kiểm tra cú pháp và định dạng
uv run ruff check src/agent-service src/ocr-service
```

---

## 📊 Giám Sát Và Trực Quan Hóa Hoạt Động (Langfuse Observability)

Langfuse giúp bạn theo dõi toàn bộ luồng suy nghĩ (trace) của Agents, thời gian phản hồi, số lượng token tiêu thụ và các công cụ được gọi.

```
                  ┌──────────────────────┐
                  │   Agent Service      │
                  │ (FastAPI / LangGraph)│
                  └──────────┬───────────┘
                             │
                             │ (Gửi telemetry qua HTTPS)
                             ▼
                  ┌──────────────────────┐
                  │ Langfuse Web (:3000) │
                  │      Dashboard       │
                  └──────────────────────┘
```

### Hướng dẫn kích hoạt:
1. Đảm bảo docker compose chạy cả service `langfuse-web`.
2. Truy cập [http://localhost:3000](http://localhost:3000), đăng ký tài khoản admin đầu tiên.
3. Tạo một dự án mới (Project), ví dụ: `Insurance Claims Processing`.
4. Đi tới phần **Settings** -> **API Credentials** tạo cặp khóa mới.
5. Sao chép các khóa này và cập nhật vào file `.env` ở thư mục gốc:
   ```env
   LANGFUSE_ENABLED=true
   LANGFUSE_PUBLIC_KEY=pk-lf-...
   LANGFUSE_SECRET_KEY=sk-lf-...
   LANGFUSE_HOST=http://localhost:3000  # Hoặc địa chỉ IP server của bạn
   ```
6. Khởi động lại Agent Service. Các phiên chạy workflow mới sẽ tự động được ghi lại đầy đủ trên trang Langfuse Dashboard.

---

## 📈 Đánh Giá Chất Lượng (Evaluation)

Bộ công cụ đánh giá (Evaluation Toolkit) được thiết kế nhằm đo lường độ chính xác của OCR và kết quả thẩm định của các Agent dựa trên bộ dữ liệu kiểm thử chuẩn.

1. **Chạy đánh giá hàng loạt (Batch Evaluation)**:
   ```bash
   uv run python -m eval run --skip-existing --build-suggestions
   ```
2. **Tính toán các chỉ số chất lượng (Metrics)**:
   ```bash
   uv run python -m eval metrics --multi-results eval/results/claims
   ```
*Kết quả chi tiết và các biểu đồ phân tích sẽ được ghi nhận tại thư mục [eval/README.md](eval/README.md).*

---

## 📂 Danh Mục Tài Liệu Chi Tiết Trong Dự Án

Để tìm hiểu sâu hơn về thiết kế kỹ thuật của từng cấu phần, bạn có thể tham khảo các tài liệu nội bộ sau:

- **Agent Service & Kiến trúc LangGraph**: [src/agent-service/README.md](src/agent-service/README.md)
- **Logic Phân Lớp của Agent Service**: [src/agent-service/docs/README.md](src/agent-service/docs/README.md)
- **Thiết Kế Kỹ Năng Agent**: [src/agent-service/skill-based-design.md](src/agent-service/skill-based-design.md)
- **Giao Diện Streamlit & HITL**: [src/agent-service/interfaces/web/README.md](src/agent-service/interfaces/web/README.md)
- **OCR Service & Pipeline Phân Loại/Trích Xuất 2 Pha**: [src/ocr-service/README.md](src/ocr-service/README.md)
- **Hạ Tầng MongoDB**: [infrastructure/mongodb/README.md](infrastructure/mongodb/README.md)
- **Tài Liệu Đánh Giá Thực Nghiệm**: [eval/README.md](eval/README.md)

---

## 📄 Bản Quyền & Giấy Phép

Dự án này được phát hành dưới giấy phép mã nguồn mở **MIT License** - xem chi tiết tại file [LICENSE](LICENSE).
