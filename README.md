# 5bit-TuTuMCP

FastAPI service exposing a LangChain agent backed by OpenAI.

## Setup

The backend requires Python 3.12+.

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
```

Create `backend/.env` from the example and set `OPENAI_API_KEY`:

```bash
cp .env.example .env
```

## Run

```bash
cd backend
source .venv/bin/activate
fastapi dev
```

OpenAPI documentation is available at <http://127.0.0.1:8000/docs>.

Send a message to the agent:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/agent/chat \
  -H 'Content-Type: application/json' \
  -d '{"message":"Hello!"}'
```

## Test

```bash
cd backend
source .venv/bin/activate
pytest
```
