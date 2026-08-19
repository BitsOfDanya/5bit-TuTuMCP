# Jarvell AI Service

Stateless FastAPI service that owns all LLM-facing behavior:

- the LangGraph `planner -> executor -> finalizer` workflow;
- OpenAI chat and structured output;
- Markdown response generation;
- passenger document extraction;
- the `negotiate_constraints` tool backed by `constraint-negotiator`.

The service does not store users or chat history. The main backend sends the complete
conversation and current normalized trip on every request.

## Project structure

```text
app/
├── api/                    # HTTP contracts, dependencies, validation, routes
│   └── routes/             # chat, documents, health
├── agent/                  # LangGraph plan-and-execute workflow
│   └── tools/              # deterministic tools and their registry
├── core/                   # settings and internal API authentication
├── domain/                 # travel and passenger-document models/rules
├── integrations/           # OpenAI and constraint-negotiator adapters
└── main.py                 # FastAPI application factory
```

Dependencies point inward: routes depend on the domain and use injected application
services; external clients remain behind `integrations`. The service stays stateless.

## Run locally

```bash
cd ai-service
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
cp .env.example .env
fastapi dev
```

The service listens on `http://127.0.0.1:8020`. During migration it can read the existing
`OPENAI_API_KEY` from `../backend/.env`; values in `ai-service/.env` take precedence.

Start `constraint-negotiator` on port `8010` to enable real journey search and constraint
relaxation. If it is unavailable, the chat intake continues and reports search as temporarily
unavailable instead of failing the whole agent run.

## Internal API

- `POST /api/v1/ai/chat`
- `POST /api/v1/ai/documents/extract`
- `GET /health`

Set the same non-empty `INTERNAL_API_TOKEN` here and `AI_SERVICE_TOKEN` in the backend to
protect the internal endpoints outside local development.
