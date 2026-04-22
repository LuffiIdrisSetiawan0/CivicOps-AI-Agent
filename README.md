# CivicOps AI Agent

AI portfolio project for civic operations analytics. The app combines a FastAPI backend, a static dashboard, SQL analytics, policy retrieval, mock regional risk signals, guardrails, and golden-question evaluation over a safe synthetic dataset.

![Python 3.11](https://img.shields.io/badge/Python-3.11-3776AB?style=flat-square&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-Backend-009688?style=flat-square&logo=fastapi&logoColor=white)
![pytest](https://img.shields.io/badge/pytest-29%20passed-0A9EDC?style=flat-square&logo=pytest&logoColor=white)
![Render](https://img.shields.io/badge/Deploy-Render-46E3B7?style=flat-square&logo=render&logoColor=000000)

The internal product name is **SatuData Ops Agent**, inspired by Indonesian public-sector data operations.

## At A Glance

| Area | What is included |
| --- | --- |
| Backend | FastAPI, Pydantic, SQLAlchemy, SQLite |
| AI workflow | Router/supervisor, SQL analyst, document/RAG agent, quality checker |
| OpenAI mode | Chat mode and answer polishing when `OPENAI_API_KEY` is configured |
| Offline mode | Deterministic routing, SQL templates, lexical document retrieval |
| Frontend | Static dashboard with chat, traces, KPIs, and evaluation controls |
| Safety | Read-only SQL guardrails and synthetic publish-safe data |
| Validation | Ruff plus 29 pytest tests |
| Deployment | Dockerfile and Render blueprint |

## What It Does

Users can ask operational questions in Indonesian or English:

- Which region and service have the highest backlog?
- Which services are over SLA?
- What is the escalation policy for high-severity complaints?
- Which budget programs have low realization?
- What operational risk should be prioritized for a specific region?

The agent routes each question to the right path:

- **SQL analytics** for KPI, complaint, budget, region, and service metrics.
- **Policy retrieval** for governance, SLA, budget, and data quality documents.
- **Mock regional signals** for synthetic flood and network-risk context.
- **Hybrid reasoning** when a question needs both metrics and policy.
- **Guardrails** for destructive SQL or unsupported data requests.

## Runtime Modes

| Mode | Behavior |
| --- | --- |
| `fast` | Local deterministic pipeline. No OpenAI call required. |
| `chat` | GPT-like conversation with local evidence for civic operations questions. |
| `polish` | Runs the local grounded answer first, then uses OpenAI to improve wording. |

If `OPENAI_API_KEY` is not configured, the app remains usable in `fast` mode.

## Quick Start

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
uvicorn app.main:app --reload
```

Open:

```text
http://127.0.0.1:8000
```

Optional OpenAI configuration:

```powershell
$env:OPENAI_API_KEY="your_key_here"
$env:OPENAI_MODEL="gpt-5-mini"
uvicorn app.main:app --reload
```

Do not commit `.env`. Use `.env.example` as the public template.

## API

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `GET` | `/api/health` | Runtime status |
| `POST` | `/api/chat` | Ask the agent a question |
| `GET` | `/api/dashboard/summary` | KPI snapshot and suggested questions |
| `GET` | `/api/datasets/preview` | Preview synthetic tables and policy docs |
| `POST` | `/api/eval/run` | Run the golden-question evaluation |

Example:

```powershell
Invoke-RestMethod -Method Post `
  -Uri http://127.0.0.1:8000/api/chat `
  -ContentType "application/json" `
  -Body '{"question":"Gabungkan backlog dan aturan eskalasi SLA untuk rekomendasi operasi.","include_trace":true,"answer_mode":"chat"}'
```

## Evaluation

Run the same checks used locally before publishing:

```powershell
python -m ruff check .
python -m pytest
```

Current local result:

```text
Ruff: all checks passed
Pytest: 29 passed
Golden questions: 20/20 passed
```

The evaluation covers SQL analytics, policy retrieval, hybrid SQL plus document reasoning, regional risk questions, and destructive SQL guardrail behavior.

## Deployment

This repository includes:

- `Dockerfile` for containerized hosting.
- `render.yaml` for Render blueprint deployment.
- `.env.example` for hosted environment configuration.

Required hosted environment variables:

- `OPENAI_API_KEY` optional for local fallback mode, recommended for GPT-like chat mode.
- `OPENAI_MODEL`
- `EMBEDDING_MODEL`
- `DATABASE_URL`
- `CHROMA_PATH`

Detailed notes: [docs/deployment.md](docs/deployment.md)

## Repository Map

```text
app/
  main.py              FastAPI app and API routes
  models.py            SQLAlchemy ORM models
  schemas.py           Pydantic request and response schemas
  data_seed.py         synthetic data and policy bootstrap
  services/
    agent.py           routing, tool orchestration, answer composition
    sql_tool.py        read-only SQL validation and analytical templates
    rag.py             document retrieval and lexical fallback
    mock_api.py        synthetic regional signal tool
    eval.py            golden-question evaluation harness
data/policies/         synthetic policy documents
docs/                  architecture, demo, deployment, and response notes
static/                dashboard UI
tests/                 pytest coverage
```

## Documentation

- [Architecture](docs/architecture.md)
- [Demo questions](docs/demo_questions.md)
- [Demo video script](docs/demo_video_script.md)
- [Agent response guidelines](docs/agent_response_guidelines.md)
- [Deployment notes](docs/deployment.md)

## Known Limitations

- This is an MVP portfolio project, not a production government system.
- The dataset is synthetic and intentionally small.
- SQLite is acceptable for the demo; long-running public hosting should use persistent storage or managed Postgres.
- Public deployment should add authentication, rate limiting, structured logging, request timeouts, and stronger observability.
