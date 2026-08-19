# Production deployment

Production consists of six containers behind Caddy:

```text
Internet -> Caddy (TLS + React SPA) -> backend -> ai-service -> constraint-negotiator -> Tutu MCP
                                          +-> trip-rescue -> Tutu MCP / OpenAI
                                          +-> smart-trip-tracker -> Tutu MCP
                                          +-> persistent application volumes
```

Only Caddy publishes host ports. The five Python services use a private Docker network with
outbound access for OpenAI and Tutu MCP,
all six services run as unprivileged users with a read-only root filesystem, drop Linux capabilities and
have health checks. Caddy obtains and renews public TLS certificates automatically.

## 1. Server and DNS

Use a Linux server with Docker Engine 24+ and the Compose v2 plugin. Point the domain's A/AAAA
records to the server and allow inbound TCP 80/443 and UDP 443. Keep ports 8000, 8001, 8010, 8020 and 8030
closed; they are not published by Compose.

## 2. Production environment

Create an ignored production env file:

```bash
cp .env.production.example .env.production
chmod 600 .env.production
```

Set `APP_DOMAIN`, `PUBLIC_ORIGIN`, `ACME_EMAIL`, the image coordinates and the OpenAI key.
Generate independent application secrets:

```bash
openssl rand -hex 32  # AUTH_SECRET_KEY
openssl rand -hex 32  # AI_SERVICE_TOKEN
```

Never commit `.env.production`. Keep `AUTH_DEBUG=false`. Use an immutable `IMAGE_TAG`, preferably
the `sha-...` tag published by CI, so rollback is deterministic.

## 3. Build and publish images

Log in to the registry and publish all six images:

```bash
docker login ghcr.io
make prod-push ENV_FILE=.env.production
```

The repository also contains `.github/workflows/production-images.yml`. Pushes to `main`, version
tags and manual runs publish multi-architecture GHCR images tagged with the commit SHA. Grant the
repository workflow permission to write packages.

## 4. Deploy

On the server, copy the repository (the Compose file and scripts are sufficient), create
`.env.production`, then run:

```bash
make prod-deploy ENV_FILE=.env.production
./scripts/smoke-production.sh https://travel.example.com
```

Deployment pulls the selected immutable image tag, applies Alembic migrations, starts services in
dependency order and waits for health checks. Re-running the command is idempotent.

For a production-like local build, set `APP_DOMAIN=http://localhost` and `PUBLIC_ORIGIN=http://localhost`
and run `make prod-up ENV_FILE=.env.production`.

## Operations

Inspect status and logs:

```bash
docker compose --env-file .env.production -f compose.prod.yaml ps
docker compose --env-file .env.production -f compose.prod.yaml logs -f --tail=200
```

Create backups of the persistent application state:

```bash
make prod-backup ENV_FILE=.env.production
```

Backups are written to the ignored `backups/` directory. Copy them to encrypted off-server storage
and test restores regularly. To roll back application code, select the previous immutable
`IMAGE_TAG` in `.env.production` and rerun `make prod-deploy`. Database rollback should use a tested
backup and a migration-specific procedure.

Because the current database is SQLite, run exactly one backend replica. Before horizontal scaling,
migrate persistence to PostgreSQL and use a distributed limiter for constraint-negotiator.

## Secret incident

An OpenAI key was previously committed in `trip-rescue/.env.example`. The file is sanitized now,
but removing it from the current tree does not remove it from Git history. Revoke that old key and,
if the repository has ever left the machine, rewrite the history with `git filter-repo` or BFG and
coordinate the force-push with all contributors.
