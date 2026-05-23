# Setup local — Day 1

Mục tiêu: clone repo → upload sample DOCX → tải translated DOCX trong **dưới 1 giờ**.

## 1. Prerequisites

| Tool | Bắt buộc? | Version | Note |
|---|---|---|---|
| **Docker Desktop** | ✅ | Latest | Linux / macOS / Windows + WSL2 |
| **git** | ✅ | 2.30+ | |
| **uv** | Optional | Latest | Chỉ cần nếu chạy backend ngoài Docker (rare) |
| **Node.js 20** | Optional | 20.x | Chỉ cần nếu chạy frontend ngoài Docker |
| **Python 3.12** | Optional | 3.12.x | Chỉ cần cho local pytest |
| AI agent (Claude Code / Cursor / Copilot / …) | Recommended | — | Cần cho Spec-Kit workflow — xem [workflow.md](workflow.md) |

Khuyên dùng Docker for all — tránh "works on my machine".

## 2. DashScope International API Key (quan trọng)

⚠️ **PHẢI là key international**, không phải key China region. Key sai → 401 cryptic, mất giờ debug.

1. Truy cập **https://dashscope-intl.aliyuncs.com** (chú ý `-intl`).
2. Đăng ký tài khoản Alibaba Cloud (cần email + thẻ verify, không tốn tiền nếu chỉ free tier).
3. Vào **API Keys** → **Create API Key** → copy key (bắt đầu bằng `sk-`).
4. Free tier: ~60 RPM với `qwen-mt-turbo` — đủ cho dev local.
5. Cost ước tính cho dev: < $1/tháng với usage bình thường.

Không share key qua chat / commit. Mỗi dev tự tạo key riêng (decision).

## 3. Clone + configure

```bash
git clone <repo-url> ai-translation
cd ai-translation

# Copy env template
cp .env.example .env
```

Mở `.env` và sửa **tối thiểu**:

```ini
DASHSCOPE_API_KEY=sk-<key của bạn>
```

Các biến khác có default OK cho dev. Đọc comment trong `.env.example` để biết khi nào cần tune.

## 4. Start stack

```bash
docker compose up --build
```

Lần đầu: ~5-10 phút (download images + PaddleOCR bake models ~1GB).

Khi thấy log như sau là OK:

```
api-1       | INFO:     Application startup complete.
worker-1    | INFO:    Starting worker for functions translate_job
web-1       | ▲ Next.js 16.x.x
web-1       | - Local: http://localhost:3000
```

(Lưu ý web container expose port host **8080**, không phải 3000 — vì 3000 conflict với Windows process trên máy owner. Xem `docker-compose.yml`.)

## 5. Migrate DB

Mở terminal khác (giữ compose chạy):

```bash
docker compose exec api alembic upgrade head
```

Output: `INFO  [alembic.runtime.migration] Will assume non-transactional DDL.` + danh sách migration → `Ok`.

Verify:

```bash
docker compose exec postgres psql -U postgres -d aitranslation -c "\dt"
```

Phải thấy các bảng: `jobs`, `segments`, `segment_flags`, `glossaries`, `glossary_terms`, `alembic_version`.

## 6. Smoke test

1. Mở **http://localhost:8080**.
2. Click **Upload** → chọn 1 file `.docx` nhỏ (vài KB), ví dụ `backend/tests/fixtures/sample.docx` nếu có.
3. Source language: `auto` | Target language: `Vietnamese`.
4. Submit → redirect sang job status page.
5. Theo dõi progress bar — segments translated tăng dần qua SSE.
6. Khi status = `done` → click **Download** → mở file translated bằng Word/LibreOffice → confirm có text Việt.

Nếu cả 6 bước OK → setup xong. 🎉

## 7. Cài AI agent (recommended)

Project dùng **Spec-Kit** workflow — đọc chi tiết ở [workflow.md](workflow.md).

Quick setup (chọn 1 agent của bạn):

```bash
# Claude Code (mặc định)
specify init . --here --integration claude --ignore-agent-tools

# Cursor
specify init . --here --integration cursor --ignore-agent-tools

# Copilot
specify init . --here --integration copilot --ignore-agent-tools

# Xem full list
specify integration list
```

`specify` CLI install 1 lần global:

```bash
uv tool install specify-cli --from git+https://github.com/github/spec-kit.git@<latest_tag>
```

Latest tag: https://github.com/github/spec-kit/releases.

## Troubleshoot

### 401 từ DashScope

→ Key đang dùng là China region. Tạo lại key trên **dashscope-intl.aliyuncs.com**.

### `worker` container "pull access denied"

→ Race condition khi compose pull image worker trước khi api build xong. Đã fix trong `docker-compose.prod.yml` (worker có `build:` riêng + `pull_policy: never`). Nếu lỗi xảy ra trong dev compose, build api trước:

```bash
docker compose build api
docker compose up -d
```

### CORS error trong browser console (dev)

→ `CORS_ALLOWED_ORIGINS` trong `.env` chưa include origin frontend. Default đã set `http://localhost:3000`, nhưng web container expose port `8080`. Sửa `.env`:

```ini
CORS_ALLOWED_ORIGINS=http://localhost:3000,http://localhost:8080
```

Restart api:

```bash
docker compose restart api
```

### "no such table: jobs" / "relation does not exist"

→ Quên chạy alembic. Quay lại bước 5.

### Translation rất chậm / rate-limited

→ Free tier DashScope ~60 RPM. `WORKER_CONCURRENCY=1` + `DASHSCOPE_PACE_SECONDS=1.2` (default) là an toàn cho free. Bump lên `WORKER_CONCURRENCY=4` chỉ khi có paid tier.

### Build PaddleOCR fail / slow

→ Network chậm hoặc Alibaba index unstable. Retry. Nếu vẫn fail, comment tạm 2 RUN block trong `backend/Dockerfile` liên quan paddlepaddle/paddleocr — backend chạy được nhưng scanned PDF sẽ không hoạt động. KHÔNG commit thay đổi này.

### Port 5432 / 6379 conflict trên máy

→ Có Postgres/Redis khác đang chạy host. Edit `docker-compose.yml`, đổi host port mapping:

```yaml
postgres:
  ports:
    - "5433:5432"   # 5433 thay vì 5432
```

Container-internal hostname `postgres` không đổi, code không cần sửa.

### Frontend không hot-reload

→ Volume mount bind đường dẫn có khác biệt OS path (Windows backslash). Restart web container:

```bash
docker compose restart web
```

## Working without Docker (advanced)

Chỉ làm khi cần debug deep hoặc Docker không khả dụng. Đọc `README` của `backend/` + `frontend/` (nếu có), hoặc:

**Backend**:
```bash
cd backend
uv pip install --system -e ".[test]"
# Cần postgres + redis chạy local riêng
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/aitranslation \
  REDIS_URL=redis://localhost:6379/0 \
  DASHSCOPE_API_KEY=sk-... \
  uvicorn app.main:app --reload
```

**Frontend**:
```bash
cd frontend
npm install
BACKEND_URL=http://localhost:8000 npm run dev
```

PaddleOCR install ngoài Docker phức tạp — xem `backend/Dockerfile` lines 27-44 để biết chính xác commands.

## Tiếp theo

→ [architecture.md](architecture.md) để hiểu code layout.
→ [workflow.md](workflow.md) để biết cách contribute.
