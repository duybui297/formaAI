---
phase: 01-foundation-docx-pipeline
plan: "01"
type: execute
wave: 0
depends_on: []
files_modified:
  - docker-compose.yml
  - .env.example
  - .gitignore
  - Makefile
  - backend/pyproject.toml
  - backend/Dockerfile
  - backend/.dockerignore
  - frontend/package.json
  - frontend/next.config.mjs
  - frontend/tsconfig.json
  - scripts/healthcheck.py
autonomous: false
requirements:
  - INFRA-01
  - INFRA-02
  - INFRA-03
  - INFRA-04
  - INFRA-05
  - LANG-02

must_haves:
  truths:
    - "docker compose up starts api, worker, web, postgres, redis without error"
    - "healthcheck.py verifies DashScope reachability and terminology param behavior"
    - "Noto CJK and Noto Sans fonts are installed in the backend Docker image"
    - "backend pyproject.toml has all Phase 1 Python dependencies pinned"
    - "frontend package.json has Next.js 16.2.3, React 19, TanStack Query 5, fetch-event-source"
  artifacts:
    - path: "docker-compose.yml"
      provides: "Service topology: api, worker, web, postgres, redis"
    - path: ".env.example"
      provides: "All required env vars documented with descriptions"
    - path: "backend/pyproject.toml"
      provides: "Python dependencies for backend (fastapi, arq, sqlalchemy, openai, etc.)"
    - path: "backend/Dockerfile"
      provides: "Python 3.12-slim-bookworm image with Noto fonts"
    - path: "frontend/package.json"
      provides: "Next.js 16.2.3 + React 19 + shadcn dependencies"
    - path: "scripts/healthcheck.py"
      provides: "INFRA-01/02 DashScope + terminology + DB + Redis + font checks"
  key_links:
    - from: "docker-compose.yml api service"
      to: "backend/src/app/main.py"
      via: "uvicorn entrypoint"
    - from: "docker-compose.yml worker service"
      to: "backend/src/app/workers/translate_worker.py"
      via: "arq entrypoint"
    - from: "scripts/healthcheck.py"
      to: "dashscope-intl.aliyuncs.com"
      via: "openai SDK AsyncOpenAI"

user_setup:
  - service: DashScope International
    why: "Translation engine for qwen-mt-turbo"
    env_vars:
      - name: DASHSCOPE_API_KEY
        source: "Alibaba Cloud International Console (dashscope-intl.aliyuncs.com) → API Keys. MUST be international key, NOT China key"
    dashboard_config:
      - task: "Enable Docker Desktop WSL2 integration"
        location: "Docker Desktop → Settings → Resources → WSL Integration → enable for your WSL2 distro. Verify with: docker ps from WSL shell"
---

<objective>
Bootstrap the entire project infrastructure: Python backend (pyproject.toml, Dockerfile), Next.js 16 frontend (package.json, config), docker-compose topology, environment configuration, and the INFRA-01/02 healthcheck script.

Purpose: Provide the scaffold every subsequent plan depends on. Without this plan, no code can run.
Output: A docker-compose.yml that brings up all 5 services, a backend image with Noto fonts, frontend with shadcn initialized, and a healthcheck script that validates DashScope + terminology API + DB + Redis + fonts.

WAVE 0 MANUAL PREREQUISITE: Before running docker compose up, Thu must enable Docker Desktop WSL2 integration. Docker Desktop → Settings → Resources → WSL Integration → toggle on for the active WSL2 distro → Apply. Verify with `docker ps` from WSL shell. This is a human-action checkpoint — cannot be automated.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/ROADMAP.md
@.planning/phases/01-foundation-docx-pipeline/01-CONTEXT.md
@.planning/phases/01-foundation-docx-pipeline/01-RESEARCH.md
@.planning/phases/01-foundation-docx-pipeline/01-AI-SPEC.md

<interfaces>
<!-- Key decisions from CONTEXT.md for this plan -->

D-01: Monorepo with backend/ + frontend/ dirs. Single docker-compose.yml + .env.example at root.
D-02: Backend Python package layout: src/app/{api,services,pipeline,db,core,workers}/... with main.py FastAPI entry, workers/translate_worker.py arq entry.
D-03: docker-compose services: api (uvicorn --reload + bind-mount backend/src), worker (arq, same image), web (Next.js dev + bind-mount frontend/src), postgres, redis. Single docker-compose up. Pin pgdata volume.
D-18: scripts/healthcheck.py checks DashScope intl + qwen-mt-turbo + terminology param + Postgres + Redis + Noto fonts.
D-19: structlog JSON to stdout; job_id bound as context var.
D-20: Next.js ^16.2.3 + React 19. Turbopack default. No webpack config.

Stack (locked from CLAUDE.md + RESEARCH.md):
  backend: python:3.12-slim-bookworm, fastapi>=0.115, arq==0.27.0, sqlalchemy[asyncio]>=2.0,
           openai>=1.40<2, tiktoken, sse-starlette==3.3.4, pydantic-settings>=2, structlog,
           redis[hiredis]>=5, python-docx==1.2.0, python-multipart, uvicorn[standard], asyncpg>=0.30, alembic>=1.13
  frontend: next@^16.2.3, react@19, @tanstack/react-query@^5, @microsoft/fetch-event-source@^2,
            shadcn/ui (New York style, Slate base), lucide-react, tailwindcss@^3

Dockerfile pattern (RESEARCH.md §12):
  FROM python:3.12-slim-bookworm
  RUN apt-get update && apt-get install -y --no-install-recommends fonts-noto-cjk fonts-noto && fc-cache -f && rm -rf /var/lib/apt/lists/*

Healthcheck items (D-18):
  1. DashScope intl endpoint reachable + qwen-mt-turbo responds to 1-sentence VN→EN probe
  2. terminology param behavior documented (term present vs absent in output)
  3. Postgres reachable + Alembic migrations at head (Phase 1: no migrations yet, just connectivity)
  4. Redis reachable + arq queue writable
  5. Noto CJK + Noto Sans fonts present at /usr/share/fonts/opentype/noto/ (Debian bookworm path)
</interfaces>
</context>

<tasks>

<task type="checkpoint:human-action" gate="blocking">
  <name>Task 1: Enable Docker Desktop WSL2 Integration</name>
  <what-built>N/A — this is a prerequisite action only Thu can perform</what-built>
  <how-to-verify>
    1. Open Docker Desktop on Windows
    2. Go to Settings → Resources → WSL Integration
    3. Toggle on WSL2 integration for your active distro (e.g. Ubuntu-22.04 or Debian)
    4. Click "Apply & Restart"
    5. From WSL terminal: run `docker ps` — should return an empty table, not an error
    6. Run `docker compose version` — should return "Docker Compose version v2.x.x"
  </how-to-verify>
  <resume-signal>Type "docker ready" after `docker ps` returns successfully from WSL shell</resume-signal>
</task>

<task type="auto">
  <name>Task 2: Create Backend Project Scaffold</name>
  <files>
    backend/pyproject.toml
    backend/Dockerfile
    backend/.dockerignore
    .env.example
    .gitignore
    Makefile
  </files>
  <read_first>
    .planning/phases/01-foundation-docx-pipeline/01-RESEARCH.md (Standard Stack install commands, Section 12 Dockerfile, Section 6 worker)
    .planning/phases/01-foundation-docx-pipeline/01-CONTEXT.md (D-02, D-03, D-04, D-19)
    ./CLAUDE.md (Version Compatibility Notes, Installation)
  </read_first>
  <action>
Create `backend/pyproject.toml` with uv-managed Python 3.12 project. Project name: ai-translation-backend. Dependencies:

```toml
[project]
name = "ai-translation-backend"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "fastapi>=0.115,<0.116",
    "uvicorn[standard]>=0.30",
    "python-multipart>=0.0.9",
    "pydantic-settings>=2.0",
    "structlog>=24.0",
    "openai>=1.40,<2",
    "tiktoken>=0.7",
    "python-docx==1.2.0",
    "sse-starlette==3.3.4",
    "sqlalchemy[asyncio]>=2.0,<3",
    "asyncpg>=0.30",
    "alembic>=1.13",
    "arq==0.27.0",
    "redis[hiredis]>=5.0",
]

[project.optional-dependencies]
test = [
    "pytest>=8.0",
    "pytest-asyncio>=0.23",
    "pytest-cov>=5.0",
    "httpx>=0.27",
]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
addopts = "--cov=src/app --cov-report=term-missing --cov-fail-under=80"

[tool.ruff]
line-length = 88

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/app"]
```

Create `backend/Dockerfile` (RESEARCH.md §12 exact pattern, INFRA-05 fonts):
```dockerfile
FROM python:3.12-slim-bookworm

RUN apt-get update && \
    apt-get install -y --no-install-recommends fonts-noto-cjk fonts-noto && \
    fc-cache -f && \
    rm -rf /var/lib/apt/lists/*

RUN pip install uv

WORKDIR /backend

COPY pyproject.toml .
RUN uv pip install --system -e ".[test]"

COPY src/ src/

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
```

Create `backend/.dockerignore`:
```
__pycache__/
*.py[cod]
.pytest_cache/
.coverage
htmlcov/
dist/
*.egg-info/
.venv/
```

Create `.env.example` with all required vars (per D-04, security rules):
```bash
# DashScope API — use the INTERNATIONAL key from dashscope-intl.aliyuncs.com
# China-region key (from dashscope.aliyun.com) will return cryptic 401
DASHSCOPE_API_KEY=sk-your-international-key-here
DASHSCOPE_BASE_URL=https://dashscope-intl.aliyuncs.com/compatible-mode/v1

# Database
DATABASE_URL=postgresql+asyncpg://postgres:postgres@postgres:5432/aitranslation

# Redis
REDIS_URL=redis://redis:6379/0

# File storage (per D-04: per-job layout under .data/)
DATA_DIR=/data

# Token budget for qwen-mt-turbo batching (D-07: 2-4K range)
TOKEN_BUDGET=3000

# Worker concurrency (D-17: 4 concurrent batches per job)
WORKER_CONCURRENCY=4
```

Create `.gitignore` additions (append to any existing):
```
# Project-specific
.data/
*.env
.env.local
backend/.venv/
backend/dist/
frontend/.next/
frontend/node_modules/
__pycache__/
*.pyc
.pytest_cache/
htmlcov/
.coverage
```

Create `Makefile` at repo root:
```makefile
.PHONY: test test-unit test-integration lint typecheck up down

# Run backend unit tests (no external services needed)
test-unit:
	cd backend && uv run pytest tests/ -m "not integration" -x -v

# Run backend integration tests (requires Docker services up)
test-integration:
	cd backend && uv run pytest tests/ -m integration -v

# Run full test suite
test:
	cd backend && uv run pytest tests/ -v

# Lint
lint:
	cd backend && uv run ruff check src/ tests/

# Type check
typecheck:
	cd backend && uv run pyright src/

# Start all services
up:
	docker compose up --build

# Stop all services
down:
	docker compose down

# Health check
healthcheck:
	python scripts/healthcheck.py
```
  </action>
  <verify>
    <automated>
      test -f backend/pyproject.toml &amp;&amp; grep -q "python-docx==1.2.0" backend/pyproject.toml &amp;&amp;
      grep -q "arq==0.27.0" backend/pyproject.toml &amp;&amp;
      grep -q "sse-starlette==3.3.4" backend/pyproject.toml &amp;&amp;
      grep -q "fonts-noto-cjk" backend/Dockerfile &amp;&amp;
      grep -q "fc-cache" backend/Dockerfile &amp;&amp;
      grep -q "DASHSCOPE_API_KEY" .env.example &amp;&amp;
      grep -q "TOKEN_BUDGET" .env.example &amp;&amp;
      test -f Makefile &amp;&amp; grep -q "test-unit" Makefile
    </automated>
  </verify>
  <done>
    backend/pyproject.toml has all Phase 1 dependencies pinned (python-docx==1.2.0, arq==0.27.0, sse-starlette==3.3.4, openai>=1.40 under 2).
    Dockerfile installs fonts-noto-cjk and fonts-noto and runs fc-cache.
    .env.example documents DASHSCOPE_API_KEY (with warning about intl vs China key), DATABASE_URL, REDIS_URL, DATA_DIR, TOKEN_BUDGET, WORKER_CONCURRENCY.
    Makefile has test-unit, test-integration, test, lint, up, down, healthcheck targets.
  </done>
</task>

<task type="auto">
  <name>Task 3: Create docker-compose.yml and Frontend Config</name>
  <files>
    docker-compose.yml
    frontend/package.json
    frontend/next.config.mjs
    frontend/tsconfig.json
  </files>
  <read_first>
    .planning/phases/01-foundation-docx-pipeline/01-CONTEXT.md (D-01, D-03, D-04, D-20)
    .planning/phases/01-foundation-docx-pipeline/01-RESEARCH.md (Section 9 Next.js 16 patterns, Standard Stack frontend install)
    .planning/phases/01-foundation-docx-pipeline/01-UI-SPEC.md (Design System: Next.js 16.2.3, React 19, shadcn New York/Slate)
  </read_first>
  <action>
Create `docker-compose.yml` (D-03 topology exactly):
```yaml
version: "3.9"

services:
  api:
    build:
      context: ./backend
      dockerfile: Dockerfile
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
    volumes:
      - ./backend/src:/backend/src
      - ./.data:/data
    env_file: .env
    environment:
      - DATA_DIR=/data
    ports:
      - "8000:8000"
    depends_on:
      - postgres
      - redis

  worker:
    build:
      context: ./backend
      dockerfile: Dockerfile
    command: arq app.workers.translate_worker.WorkerSettings
    volumes:
      - ./backend/src:/backend/src
      - ./.data:/data
    env_file: .env
    environment:
      - DATA_DIR=/data
    depends_on:
      - postgres
      - redis

  web:
    build:
      context: ./frontend
      dockerfile: Dockerfile.frontend
    command: npm run dev
    volumes:
      - ./frontend/src:/frontend/src
      - ./frontend/public:/frontend/public
    environment:
      - NEXT_PUBLIC_API_URL=http://localhost:8000
      - BACKEND_URL=http://api:8000
    ports:
      - "3000:3000"
    depends_on:
      - api

  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: aitranslation
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"

volumes:
  pgdata:
```

Create `frontend/package.json` with exact versions per D-20 and UI-SPEC:
```json
{
  "name": "ai-translation-frontend",
  "version": "0.1.0",
  "private": true,
  "scripts": {
    "dev": "next dev --turbopack",
    "build": "next build",
    "start": "next start",
    "lint": "next lint",
    "type-check": "tsc --noEmit"
  },
  "dependencies": {
    "next": "^16.2.3",
    "react": "^19.0.0",
    "react-dom": "^19.0.0",
    "@tanstack/react-query": "^5.0.0",
    "@microsoft/fetch-event-source": "^2.0.1",
    "lucide-react": "^0.400.0",
    "class-variance-authority": "^0.7.0",
    "clsx": "^2.1.0",
    "tailwind-merge": "^2.3.0",
    "tailwindcss-animate": "^1.0.7"
  },
  "devDependencies": {
    "@types/node": "^20",
    "@types/react": "^19",
    "@types/react-dom": "^19",
    "typescript": "^5",
    "tailwindcss": "^3.4.0",
    "autoprefixer": "^10.4.0",
    "postcss": "^8.4.0",
    "eslint": "^8",
    "eslint-config-next": "^16.2.3"
  }
}
```

Create `frontend/next.config.mjs` (D-20: Turbopack default, no webpack config):
```javascript
/** @type {import('next').NextConfig} */
const nextConfig = {
  // D-20: Turbopack is default in Next.js 16; no webpack config
  // CORS: Next.js proxies to FastAPI via app/api/upload/route.ts
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${process.env.BACKEND_URL || "http://api:8000"}/:path*`,
      },
    ];
  },
};

export default nextConfig;
```

Create `frontend/tsconfig.json` (strict, App Router compatible):
```json
{
  "compilerOptions": {
    "lib": ["dom", "dom.iterable", "esnext"],
    "allowJs": true,
    "skipLibCheck": true,
    "strict": true,
    "noEmit": true,
    "esModuleInterop": true,
    "module": "esnext",
    "moduleResolution": "bundler",
    "resolveJsonModule": true,
    "isolatedModules": true,
    "jsx": "preserve",
    "incremental": true,
    "plugins": [
      {
        "name": "next"
      }
    ],
    "paths": {
      "@/*": ["./src/*"]
    }
  },
  "include": ["next-env.d.ts", "**/*.ts", "**/*.tsx", ".next/types/**/*.ts"],
  "exclude": ["node_modules"]
}
```

Also create `frontend/Dockerfile.frontend` for docker-compose web service:
```dockerfile
FROM node:20-alpine
WORKDIR /frontend
COPY package.json package-lock.json* ./
RUN npm ci
COPY . .
EXPOSE 3000
```
  </action>
  <verify>
    <automated>
      grep -q "postgres:16-alpine" docker-compose.yml &amp;&amp;
      grep -q "redis:7-alpine" docker-compose.yml &amp;&amp;
      grep -q "pgdata" docker-compose.yml &amp;&amp;
      grep -q "arq app.workers.translate_worker.WorkerSettings" docker-compose.yml &amp;&amp;
      grep -q "\"next\": \"\\^16.2.3\"" frontend/package.json &amp;&amp;
      grep -q "fetch-event-source" frontend/package.json &amp;&amp;
      grep -q "turbopack" frontend/next.config.mjs || grep -q "turbo" frontend/package.json
    </automated>
  </verify>
  <done>
    docker-compose.yml has 5 services: api (uvicorn --reload), worker (arq WorkerSettings), web (next dev --turbopack), postgres:16-alpine, redis:7-alpine. pgdata volume persists across restarts.
    frontend/package.json pins next@^16.2.3, react@^19, @tanstack/react-query@^5, @microsoft/fetch-event-source@^2.
    frontend/next.config.mjs uses no webpack config (Turbopack default per D-20).
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 4: Create DashScope Healthcheck Script</name>
  <files>
    scripts/healthcheck.py
    scripts/__init__.py
  </files>
  <read_first>
    .planning/phases/01-foundation-docx-pipeline/01-CONTEXT.md (D-18: healthcheck checklist items)
    .planning/phases/01-foundation-docx-pipeline/01-AI-SPEC.md (Section 3: client initialisation, Section 4: terminology pattern)
    .planning/phases/01-foundation-docx-pipeline/01-RESEARCH.md (Section 11: quirks, Section 12: font paths)
  </read_first>
  <behavior>
    - Check 1: DashScope intl endpoint reachable — OpenAI sync client probes with 1-sentence VN→EN translation
    - Check 2: If key is China-region key (wrong endpoint), surface specific message: "Use the key from dashscope-intl.aliyuncs.com, not the China console"
    - Check 3: terminology param behavior — translate same sentence with and without a term; document output difference
    - Check 4: Postgres connectivity — psycopg2 or asyncpg connect to DATABASE_URL
    - Check 5: Redis connectivity — redis-py ping
    - Check 6: Noto CJK font present at /usr/share/fonts/opentype/noto/ (fc-list check)
    - Exit 0 on all pass, exit 1 on any failure with clear error message
  </behavior>
  <action>
Create `scripts/healthcheck.py`. This is a standalone sync script using the openai SDK sync client (not async — sync is correct for scripts per AI-SPEC §3). Checks:

1. DashScope probe (INFRA-01):
```python
from openai import OpenAI, AuthenticationError, APIConnectionError
import os, sys

def check_dashscope():
    api_key = os.environ.get("DASHSCOPE_API_KEY", "")
    base_url = os.environ.get("DASHSCOPE_BASE_URL",
                               "https://dashscope-intl.aliyuncs.com/compatible-mode/v1")
    client = OpenAI(api_key=api_key, base_url=base_url, max_retries=0, timeout=30.0)
    try:
        resp = client.chat.completions.create(
            model="qwen-mt-turbo",
            messages=[{"role": "user", "content": "Xin chào thế giới"}],
            extra_body={"translation_options": {"source_lang": "auto", "target_lang": "English"}},
            max_tokens=50,
        )
        output = resp.choices[0].message.content or ""
        print(f"[OK] DashScope intl: qwen-mt-turbo responded. Output: {output!r}")
        return True
    except AuthenticationError:
        print("[FAIL] DashScope: 401 Authentication error.")
        print("       If you used a China-region key (from dashscope.aliyun.com),")
        print("       obtain an international key from dashscope-intl.aliyuncs.com instead.")
        return False
    except APIConnectionError as e:
        print(f"[FAIL] DashScope: Cannot connect to {base_url}. Error: {e}")
        return False
```

2. Terminology probe (INFRA-02):
```python
def check_terminology():
    # Translate same sentence with and without a term, document behavior
    client = OpenAI(api_key=os.environ["DASHSCOPE_API_KEY"],
                    base_url=os.environ.get("DASHSCOPE_BASE_URL", "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"),
                    max_retries=0, timeout=30.0)
    text = "Tài liệu kỹ thuật của AICore được viết bằng tiếng Việt."

    # Without terminology
    r1 = client.chat.completions.create(
        model="qwen-mt-turbo",
        messages=[{"role": "user", "content": text}],
        extra_body={"translation_options": {"source_lang": "Vietnamese", "target_lang": "English"}},
        max_tokens=100,
    )
    without_term = r1.choices[0].message.content or ""

    # With terminology: tài liệu kỹ thuật → technical documentation
    r2 = client.chat.completions.create(
        model="qwen-mt-turbo",
        messages=[{"role": "user", "content": text}],
        extra_body={"translation_options": {
            "source_lang": "Vietnamese",
            "target_lang": "English",
            "terms": [{"source": "tài liệu kỹ thuật", "target": "technical documentation"}],
        }},
        max_tokens=100,
    )
    with_term = r2.choices[0].message.content or ""

    print(f"[OK] terminology probe:")
    print(f"     Without term: {without_term!r}")
    print(f"     With term:    {with_term!r}")
    print(f"     Term respected: {'technical documentation' in with_term}")
    return True
```

3. Database probe: connect with psycopg2 sync (available via asyncpg's sync path or libpq).
4. Redis probe: `redis.Redis.from_url(os.environ["REDIS_URL"]).ping()`.
5. Font probe: check `/usr/share/fonts/opentype/noto/` directory exists and is non-empty.

Main entrypoint: run all checks, print pass/fail for each, exit(0) if all pass, exit(1) if any fail. Add `if __name__ == "__main__":` guard.

Include a `--skip-db` flag for running the DashScope checks before docker-compose is up.
  </action>
  <verify>
    <automated>
      python -c "import ast; ast.parse(open('scripts/healthcheck.py').read()); print('syntax OK')" &amp;&amp;
      grep -q "check_dashscope" scripts/healthcheck.py &amp;&amp;
      grep -q "check_terminology" scripts/healthcheck.py &amp;&amp;
      grep -q "fonts-noto\|opentype/noto" scripts/healthcheck.py &amp;&amp;
      grep -q "AuthenticationError" scripts/healthcheck.py &amp;&amp;
      grep -q "dashscope-intl.aliyuncs.com" scripts/healthcheck.py
    </automated>
  </verify>
  <done>
    scripts/healthcheck.py passes Python syntax check.
    Contains check_dashscope() (probes VN→EN translation), check_terminology() (term present vs absent), Redis ping, font path check.
    AuthenticationError surfaces the "use international key" message explicitly.
    Exit code 0 on all pass, 1 on any failure.
    Can run with --skip-db to check DashScope alone before docker services are up.
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| developer → DashScope intl | API key in env var; never in source code |
| env vars → docker-compose | .env file must be gitignored; .env.example committed instead |
| .data/ directory | Per-job file storage; gitignored; contains user documents |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-01-01 | Information Disclosure | DASHSCOPE_API_KEY | mitigate | `.env` in .gitignore; `.env.example` has placeholder value; healthcheck warns if key looks like China key |
| T-01-02 | Information Disclosure | .data/ job files | mitigate | `.data/` in .gitignore; docker-compose bind-mounts to /data inside container, not exposed externally |
| T-01-03 | Tampering | docker-compose volumes | accept | Internal PoC; no external users; pgdata volume stays on local machine |
| T-01-04 | Denial of Service | DashScope API key misconfigured | mitigate | healthcheck.py surfaces AuthenticationError with actionable message before any pipeline code runs |
</threat_model>

<verification>
After all tasks complete:
1. `docker compose up --build` starts all 5 services without error
2. `curl http://localhost:8000/health` returns 200 (after Wave 1 api plan)
3. `curl http://localhost:3000` returns Next.js page (after Wave 4 frontend plan)
4. `python scripts/healthcheck.py --skip-db` with valid DASHSCOPE_API_KEY prints "[OK] DashScope intl" and "[OK] terminology probe"
5. `grep -r "paragraph.text = " backend/src/` returns nothing (anti-pattern not present)
</verification>

<success_criteria>
- docker-compose.yml brings up api (8000), worker, web (3000), postgres (5432), redis (6379)
- backend/pyproject.toml has all 14 Phase 1 Python deps with correct pins
- backend/Dockerfile installs fonts-noto-cjk and fonts-noto via apt-get
- frontend/package.json has next@^16.2.3 and @microsoft/fetch-event-source@^2
- scripts/healthcheck.py exits 0 when DASHSCOPE_API_KEY is valid and services are up
- .env.example documents every required env var with descriptions
</success_criteria>

<output>
After completion, create `.planning/phases/01-foundation-docx-pipeline/01-01-SUMMARY.md`
</output>
