.PHONY: setup migrate dev smoke test

setup:
	./scripts/setup-local.sh

migrate:
	cd backend && .venv/bin/python -m alembic upgrade head

dev:
	./scripts/dev.sh

smoke:
	./scripts/smoke-local.sh

test:
	cd backend && PYTHONDONTWRITEBYTECODE=1 .venv/bin/pytest -q
	cd ai-service && PYTHONDONTWRITEBYTECODE=1 .venv/bin/pytest -q
	cd constraint-negotiator && PYTHONDONTWRITEBYTECODE=1 .venv/bin/pytest -q
	cd frontend && npm test
