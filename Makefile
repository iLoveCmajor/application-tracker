.DEFAULT_GOAL := help
.PHONY: help install dev dev-api dev-web test test-unit test-api test-integration test-web lint format typecheck build check migrate migration up down clean

# Let uv use backend/.venv even when another virtualenv is active in the shell.
unexport VIRTUAL_ENV

API_PORT ?= 8000

help: ## Show this help
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk -F ':.*## ' '{printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'

install: ## Install backend and frontend dependencies
	cd backend && uv sync
	cd frontend && npm install

# `kill 0` signals the whole process group, so uvicorn and vite stop too, not just uv and npm.
dev: ## Run the API and the UI against it (Ctrl-C stops both)
	@trap 'trap - INT TERM EXIT; kill 0' INT TERM EXIT; \
	(cd backend && uv run uvicorn app.main:app --reload --port $(API_PORT)) & \
	(cd frontend && npm run dev) & \
	wait

dev-api: ## Run only the API (http://localhost:8000, docs at /docs)
	cd backend && uv run uvicorn app.main:app --reload --port $(API_PORT)

dev-web: ## Run only the UI, against the API on port 8000
	cd frontend && npm run dev

test: test-unit test-api test-integration test-web ## Run every test: unit, API, integration, frontend

test-unit: ## Backend unit tests (no database)
	cd backend && uv run pytest -q tests/unit

test-api: ## Backend endpoint tests on SQLite
	cd backend && uv run pytest -q tests/api

test-integration: ## Backend tests against PostgreSQL (Docker, or TEST_DATABASE_URL)
	cd backend && uv run pytest -q tests/integration

test-web: ## Frontend tests
	cd frontend && npm test

lint: ## Lint and check formatting of the backend
	cd backend && uv run ruff check . && uv run ruff format --check .

format: ## Format the backend
	cd backend && uv run ruff format . && uv run ruff check --fix .

typecheck: ## Type-check backend (mypy) and frontend (tsc)
	cd backend && uv run mypy
	cd frontend && npm run typecheck

build: ## Build the frontend for production
	cd frontend && npm run build

check: lint typecheck test build ## Everything CI runs

migrate: ## Apply database migrations (DATABASE_URL, default backend/tracker.db)
	cd backend && uv run alembic upgrade head

migration: ## Create a migration from changes in tables.py: make migration m="add x"
	@test -n "$(m)" || { echo 'Usage: make migration m="what changed"'; exit 1; }
	cd backend && uv run alembic revision --autogenerate -m "$(m)"

up: ## Start the whole system with PostgreSQL (http://localhost:8080)
	docker compose up --build

down: ## Stop the system (keeps the database volume)
	docker compose down

clean: ## Remove build output and caches
	rm -rf frontend/dist backend/.pytest_cache backend/.mypy_cache backend/.ruff_cache backend/.coverage
	find backend -name __pycache__ -type d -prune -exec rm -rf {} +
