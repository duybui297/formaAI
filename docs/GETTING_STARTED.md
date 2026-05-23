# AI Translation PoC — Getting Started

Hướng dẫn từng bước để chạy project từ zero.

---

## 1. Prerequisites

| Tool | Version | Ghi chú |
|------|---------|---------|
| Docker Desktop | v4.x+ | Docker Compose v2 đi kèm |
| Git | 2.x | |
| Node.js | 20+ | Chỉ cần nếu dev frontend ngoài Docker |
| `uv` | latest | Chỉ cần nếu dev backend ngoài Docker |
| `make` | — | Optional, wrapper cho docker compose + pytest |

---

## 2. Clone repo

```bash
git clone <repo-url> ai-translation
cd ai-translation
```

---

## 3. Setup environment variables

```bash
cp .env.example .env
```

Mở `.env`, điền giá trị thật:

| Var | Bắt buộc | Cách lấy |
|-----|----------|----------|
| `DASHSCOPE_API_KEY` | **Có** | Vào https://dashscope-intl.aliyuncs.com → API Keys. **Phải dùng key international** — key China-region (`dashscope.aliyun.com`) trả 401 không message. |

Các var còn lại (DB, Redis, model, batching) đã có default khớp với docker-compose. Chỉ đổi khi biết mình đang làm gì.

Chi tiết từng var: xem comment trong `.env.example`.

---

## 4. Setup fonts (cho PDF output)

Backend cần Noto fonts để render CJK + Vietnamese vào PDF. Có 2 nguồn:

**a) System fonts (PyMuPDF):** tự cài qua Dockerfile (`apt-get install fonts-noto-cjk fonts-noto`). Không cần làm gì thêm.

**b) Bundled fonts (fpdf2 — Phase 4 OCR):** cần download thủ công vào `backend/fonts/`:

```bash
# NotoSans-Regular.ttf (~500KB)
curl -L -o backend/fonts/NotoSans-Regular.ttf \
  "https://github.com/notofonts/latin-greek-cyrillic/releases/download/NotoSans-v2.013/NotoSans-v2.013.zip" \
  # Giải nén lấy NotoSans-Regular.ttf

# NotoSansCJK-Regular.ttc (~48MB)
# Download từ: https://github.com/notofonts/noto-cjk/releases
# Lấy file NotoSansCJK-Regular.ttc
```

> **Lưu ý:** fonts KHÔNG commit vào git (đã gitignore). Chỉ cần cho Phase 4 (scanned PDF). Phase 1–3 chạy bình thường không cần bước này.

---

## 5. Chạy full stack bằng Docker (khuyến nghị)

### 5.1 Build + start

```bash
make up
# hoặc:
docker compose up -d --build
```

Lần đầu build mất ~5–10 phút (download PaddleOCR models ~700MB).

### 5.2 Services

| Service | URL / Port | Vai trò |
|---------|-----------|---------|
| **web** | http://localhost:8080 | Next.js frontend (Turbopack dev server) |
| **api** | http://localhost:8000 | FastAPI backend (uvicorn `--reload`) |
| **api /docs** | http://localhost:8000/docs | Swagger UI — xem tất cả API endpoints |
| **worker** | (no port) | arq consumer — cùng Docker image với api |
| **postgres** | localhost:5432 | DB `aitranslation`, user/pass: `postgres`/`postgres` |
| **redis** | localhost:6379 | arq job queue + SSE pub/sub |

### 5.3 Kiểm tra stack hoạt động

```bash
make healthcheck
# hoặc:
python scripts/healthcheck.py
```

Healthcheck verify 5 thứ:
1. DashScope API key hợp lệ + `qwen-mt-turbo` trả kết quả
2. `terminology` param hoạt động (glossary injection)
3. PostgreSQL connect được
4. Redis connect + arq queue writable
5. Noto fonts có mặt

> **Tip:** nếu Docker chưa lên, chỉ muốn test DashScope key:
> ```bash
> python scripts/healthcheck.py --skip-db
> ```

### 5.4 Database migration

```bash
docker compose exec api alembic upgrade head
```

Migration chạy tự động nếu DB trống. Khi có migration mới (pull code):

```bash
docker compose exec api alembic upgrade head
```

Tạo migration mới:

```bash
docker compose exec api alembic revision -m "mô tả thay đổi" --autogenerate
```

### 5.5 Sử dụng app

1. Mở http://localhost:8080
2. Upload tài liệu (DOCX / PDF / PPTX)
3. Chọn source language + target language
4. (Tùy chọn) Chọn glossary
5. Bấm Upload → chuyển sang trang Jobs
6. Xem progress realtime (SSE)
7. Khi done → vào Review, sửa inline, bấm Download

### 5.6 Stop

```bash
make down
# hoặc:
docker compose down
```

> **Lưu ý:** `docker compose down` giữ volume Postgres (`pgdata`). Muốn xóa sạch DB:
> ```bash
> docker compose down -v
> ```

---

## 6. Chạy local không Docker (nâng cao)

Dùng khi cần debug sâu hoặc tốc độ hot-reload nhanh hơn Docker bind mount.

### 6.1 Backend

```bash
cd backend

# Cài deps
uv pip install -e ".[test]"

# Cần Postgres + Redis chạy riêng (docker hoặc local install)
# Sửa .env cho host-level URLs:
#   DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/aitranslation
#   REDIS_URL=redis://localhost:6379/0
#   DATA_DIR=../.data

# Migration
alembic upgrade head

# Start API server
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# Start worker (terminal riêng)
arq app.workers.translate_worker.WorkerSettings
```

### 6.2 Frontend

```bash
cd frontend
npm install

# Sửa env cho local backend:
#   NEXT_PUBLIC_API_URL=http://localhost:8000
#   BACKEND_URL=http://localhost:8000

npm run dev
# Mở http://localhost:3000
```

---

## 7. Testing

### 7.1 Backend (pytest)

```bash
# Unit tests — không cần Docker services
make test-unit
# hoặc: cd backend && uv run pytest tests/ -m "not integration" -x -v

# Integration tests — cần Docker services chạy
make test-integration
# hoặc: cd backend && uv run pytest tests/ -m integration -v

# Full suite
make test

# Eval suite (translation quality checks)
make eval
```

Test marker-based: `@pytest.mark.integration` cho test cần DB/Redis thật. Mặc định `test-unit` chạy tất cả trừ integration.

Coverage threshold: 80% (`--cov-fail-under=80` trong `pyproject.toml`).

### 7.2 Frontend (vitest + playwright)

```bash
cd frontend

# Unit + component tests
npm run test            # vitest run (one-shot)
npm run test:watch      # vitest watch mode

# E2E tests (cần full stack chạy)
npx playwright test
```

Test files co-located cạnh code (không có thư mục `__tests__/` riêng):
- `features/review/FlagBadge.test.tsx`
- `hooks/useSegments.test.ts`
- `lib/formatBreadcrumb.test.ts`
- v.v.

---

## 8. Lint + Type check + Format

### Backend

```bash
make lint        # ruff check
make typecheck   # mypy
make format      # ruff format (auto-fix)
```

Config: `pyproject.toml` → `[tool.ruff]` (line-length 88, Python 3.12, select E/F/I/UP/B/SIM).

### Frontend

```bash
cd frontend
npm run lint          # next lint (ESLint)
npm run type-check    # tsc --noEmit
```

---

## 9. Hot-reload trong Docker

Cả backend và frontend đều bind-mount source code:

| Thay đổi | Tự reload? | Ghi chú |
|----------|-----------|---------|
| `backend/src/**/*.py` | Có | uvicorn `--reload` |
| `frontend/src/**/*` | Có | Next.js Turbopack HMR |
| `pyproject.toml` | Không | Rebuild: `docker compose build api` |
| `package.json` | Không | Rebuild: `docker compose build web` |
| `docker-compose.yml` | Không | `docker compose up -d` (recreate) |
| `.env` | Không | `docker compose up -d` (recreate) |
| `Dockerfile` | Không | `docker compose build` |

---

## 10. Troubleshooting

### DashScope API trả 401

- **Nguyên nhân phổ biến:** dùng key China-region (`dashscope.aliyun.com`) thay vì international (`dashscope-intl.aliyuncs.com`). Hai hệ thống **riêng biệt**, key không dùng chung.
- **Fix:** tạo account + key tại https://dashscope-intl.aliyuncs.com

### Docker build lỗi PaddleOCR / paddlepaddle

- PaddlePaddle phải cài từ Alibaba index (PyPI version là stub).
- Dockerfile đã handle bằng `-i https://www.paddlepaddle.org.cn/packages/stable/cpu/`.
- Nếu lỗi network → check proxy / VPN.

### Alembic "Target database is not up to date"

```bash
docker compose exec api alembic upgrade head
```

### Frontend "Module not found" sau khi pull

```bash
docker compose build web
# hoặc nếu dev local:
cd frontend && npm install
```

### Worker không xử lý job (job stuck ở "queued")

1. Check worker log: `docker compose logs worker -f`
2. Check Redis: `docker compose exec redis redis-cli ping`
3. Check `.env` có `REDIS_URL` đúng

### Fonts thiếu → PDF output không có text CJK/Vietnamese

- Phase 1–3 (PyMuPDF): đã cài qua apt trong Dockerfile → tự hoạt động.
- Phase 4 (fpdf2): cần download fonts vào `backend/fonts/` (xem Section 4).
- Verify: `make healthcheck` → Check 5 phải PASS.

---

## 11. Useful commands cheat sheet

```bash
# Xem logs
docker compose logs -f api          # backend API
docker compose logs -f worker       # translation worker
docker compose logs -f web          # frontend

# Vào shell container
docker compose exec api bash
docker compose exec web sh

# Reset DB hoàn toàn
docker compose down -v && docker compose up -d && docker compose exec api alembic upgrade head

# Xem API docs
open http://localhost:8000/docs

# Xem trạng thái job qua API
curl http://localhost:8000/jobs | python3 -m json.tool

# Clear translation output
rm -rf .data/jobs/*
```
