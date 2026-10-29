.PHONY: setup lint format typecheck test test-backend test-frontend e2e migrate dev check audit

setup:
	cd backend && uv sync --all-groups

lint:
	cd backend && uv run ruff check src tests
	cd backend && uv run ruff format --check src tests

format:
	cd backend && uv run ruff format src tests
	cd backend && uv run ruff check --fix src tests

typecheck:
	cd backend && uv run mypy

test-backend:
	cd backend && uv run pytest

test: test-backend

test-frontend:
	@echo "Frontend tests are not runnable: the frontend package has not been initialized."
	@exit 1

e2e:
	@echo "End-to-end tests are not runnable: Playwright has not been initialized."
	@exit 1

migrate:
	cd backend && uv run alembic upgrade head

dev:
	docker compose -f deploy/dev/compose.yml up

check: lint typecheck test-backend audit

audit:
	cd backend && uv run bandit -c pyproject.toml -r src/supplymind
	cd backend && uv run pip-audit
