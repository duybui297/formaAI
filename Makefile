.PHONY: test test-unit test-integration lint typecheck format up down healthcheck

# Run backend unit tests (no external services needed)
test-unit:
	cd backend && uv run pytest tests/ -m "not integration" -x -v

# Run backend integration tests (requires Docker services up)
test-integration:
	cd backend && uv run pytest tests/ -m integration -v

# Run full test suite
test:
	cd backend && uv run pytest tests/ -v

# Run evaluation suite (translation quality checks)
eval:
	cd backend && uv run pytest tests/eval/ -v

# Lint backend
lint:
	cd backend && uv run ruff check src/ tests/

# Type check backend
typecheck:
	cd backend && uv run pyright src/

# Format backend
format:
	cd backend && uv run ruff format src/ tests/

# Start all services
up:
	docker compose up --build

# Stop all services
down:
	docker compose down

# Health check (validates DashScope + DB + Redis + fonts)
# Use --skip-db to check DashScope alone before docker services are up
healthcheck:
	python scripts/healthcheck.py
