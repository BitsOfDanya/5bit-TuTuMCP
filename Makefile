.PHONY: setup migrate dev smoke test prod-config prod-build prod-up prod-push prod-deploy prod-backup

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
	cd smart-trip-tracker/backend && PYTHONDONTWRITEBYTECODE=1 .venv/bin/pytest -q
	cd frontend && npm test

prod-config:
	docker compose --env-file "$${ENV_FILE:-.env.production}" -f compose.prod.yaml config --quiet

prod-build:
	./scripts/build-production.sh "$${ENV_FILE:-.env.production}"

prod-up:
	./scripts/run-production-local.sh "$${ENV_FILE:-.env.production}"

prod-push:
	./scripts/publish-production.sh "$${ENV_FILE:-.env.production}"

prod-deploy:
	./scripts/deploy-production.sh "$${ENV_FILE:-.env.production}"

prod-backup:
	./scripts/backup-production.sh "$${ENV_FILE:-.env.production}"
