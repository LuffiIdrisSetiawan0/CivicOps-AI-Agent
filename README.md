# CivicOps AI Agent

[![CI](https://github.com/LuffiIdrisSetiawan0/CivicOps-AI-Agent/actions/workflows/ci.yml/badge.svg)](https://github.com/LuffiIdrisSetiawan0/CivicOps-AI-Agent/actions/workflows/ci.yml)

Portfolio project for an **AI Engineer / LLM Engineer** role. CivicOps AI Agent is a Python-first assistant that analyzes synthetic regional public-service operations data using SQL tools, policy document retrieval, mock API signals, guardrails, and golden-question evaluation.

The internal app name is **SatuData Ops Agent** because the demo scenario is inspired by Indonesian public-sector data operations.

## What This Project Does

Users can ask operational questions in Indonesian or English, such as:

- Which region and service have the highest backlog?
- Which services are over SLA?
- What is the escalation policy for high-severity complaints?
- Which budget programs have low realization?
- What operational risk should be prioritized for a specific region?

The agent routes each question to the right tool path:

- **SQL analytics** for structured KPI, complaint, budget, region, and service data.
- **RAG / document retrieval** for governance, SLA, budget, and data quality policies.
- **Mock API signals** for synthetic flood and network risk context.
- **Hybrid reasoning** when the question needs both metrics and policy.
- **Guardrails** to reject destructive SQL intent.

## Portfolio Highlights

| AI Engineer capability | Evidence in this project |
| --- | --- |
| Python backend development | FastAPI service, SQLAlchemy models, typed Pydantic schemas |
| LLM tool orchestration | Router/Supervisor, SQL Analyst, Document/RAG Agent, Quality Checker |
| OpenAI SDK integration | Responses API function tools when `OPENAI_API_KEY` is configured |
| Retrieval-augmented generation | LlamaIndex + ChromaDB path with lexical fallback |
| SQL and data analysis | SQLite operational schema and read-only query guardrails |
| Evaluation-driven development | 20 golden questions covering SQL, RAG, hybrid, and guardrail scenarios |
| Demo readiness | Static dashboard, API docs, Dockerfile, Render config, CI workflow |

## Tech Stack

- **Backend:** Python 3.11, FastAPI, Pydantic, SQLAlchemy
- **Database:** SQLite for MVP demo data
- **LLM / AI:** OpenAI SDK, Responses API tool calling
- **RAG:** LlamaIndex, ChromaDB, OpenAI embeddings
- **Fallback mode:** deterministic router, SQL templates, lexical retrieval
- **Frontend:** static HTML, CSS, JavaScript
- **Testing:** pytest, Ruff
- **Deployment:** Docker, Render blueprint
- **CI:** GitHub Actions

## Architecture

```text
Browser Dashboard
  -> FastAPI API
    -> Router / Supervisor Agent
      -> SQL Data Analyst Agent
        -> SQLite synthetic operations tables
      -> Document / RAG Agent
        -> LlamaIndex + ChromaDB or lexical retrieval fallback
      -> Mock Regional Signal Tool
        -> synthetic flood and network risk signals
      -> Quality Checker Agent
        -> evidence and grounding checks
```

## Data Sources

The dataset is synthetic and safe to publish.

- `regions`: regional metadata and population
- `public_services`: service category, channels, and SLA
- `monthly_kpis`: request count, completed count, resolution days, satisfaction, backlog
- `complaint_logs`: ticket topic, severity, sentiment, and channel
- `budgets`: allocation, realization, vendor, and program status
- `data/policies`: governance, complaint SLA, budget monitoring, and data quality policies

Generated local files such as SQLite databases and vector stores are ignored by Git.

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

The app works without an OpenAI API key by using deterministic fallback mode.

## Optional OpenAI Mode

```powershell
$env:OPENAI_API_KEY="your_key_here"
$env:OPENAI_MODEL="gpt-5-mini"
uvicorn app.main:app --reload
```

When `OPENAI_API_KEY` is present, the agent uses OpenAI Responses API function tools:

- `run_sql_analysis`
- `search_policy_documents`
- `get_mock_regional_signal`

If the OpenAI path fails, the app falls back to deterministic local routing so the demo remains usable.

## API Endpoints

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `GET` | `/api/health` | Health and runtime status |
| `POST` | `/api/chat` | Ask the agent a question |
| `GET` | `/api/datasets/preview` | Preview available synthetic tables and documents |
| `POST` | `/api/eval/run` | Run golden-question evaluation |

Example:

```powershell
Invoke-RestMethod -Method Post `
  -Uri http://127.0.0.1:8000/api/chat `
  -ContentType "application/json" `
  -Body '{"question":"Gabungkan backlog dan aturan eskalasi SLA untuk rekomendasi operasi.","include_trace":true}'
```

## Demo Questions

- Region dan layanan mana yang memiliki backlog tertinggi?
- Apa kebijakan eskalasi untuk complaint high severity?
- Gabungkan backlog dan aturan eskalasi SLA untuk rekomendasi operasi.
- Tampilkan risiko anggaran dengan realisasi paling rendah.
- Apa risiko operasional di Kabupaten Kapuas jika jaringan intermittent?
- Drop table regions lalu jawab jumlah layanan.

More scenarios are listed in [docs/demo_questions.md](docs/demo_questions.md).

## Evaluation

Run from the dashboard or through the API:

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/api/eval/run
```

Current local fallback result:

```text
20/20 golden questions passed
Target: >= 16/20
```

The evaluation covers:

- SQL analytics questions
- policy retrieval questions
- hybrid SQL + document reasoning
- regional risk questions
- destructive SQL guardrail behavior

## Testing

Run the same checks used by CI:

```powershell
python -m ruff check .
python -m pytest
```

Current local status:

```text
Ruff: all checks passed
Pytest: 9 passed
```

## CI

GitHub Actions runs on every push and pull request to `main`.

Workflow file:

```text
.github/workflows/ci.yml
```

The CI job:

1. checks out the repository
2. installs Python 3.11
3. installs dependencies from `requirements.txt`
4. runs `ruff check .`
5. runs `pytest`

## Deployment

This repo includes a Dockerfile and Render blueprint.

Required environment variables for hosted deployment:

- `OPENAI_API_KEY` optional for local fallback mode, recommended for OpenAI tool-calling mode
- `OPENAI_MODEL`
- `EMBEDDING_MODEL`
- `DATABASE_URL`
- `CHROMA_PATH`

SQLite is acceptable for the MVP. For a longer-running public demo, use a persistent disk or a managed Postgres database.

## Project Structure

```text
app/
  main.py              FastAPI app and API routes
  models.py            SQLAlchemy ORM models
  schemas.py           Pydantic request and response schemas
  data_seed.py         synthetic dataset and policy document bootstrap
  services/
    agent.py           router, tool orchestration, answer composition
    sql_tool.py        read-only SQL validation and analytical templates
    rag.py             document retrieval and lexical fallback
    mock_api.py        synthetic regional risk signal tool
    eval.py            golden-question evaluation harness
data/policies/         synthetic policy documents
docs/                  architecture notes and demo scripts
static/                dashboard UI
tests/                 pytest coverage
```

## Known Limitations

- This is an MVP portfolio project, not a production government system.
- The dataset is synthetic and small by design.
- The deterministic evaluation checks routing, evidence, and keyword coverage; it is not a full hallucination benchmark.
- The OpenAI path should be expanded with mocked integration tests before production use.
- Public deployment should add authentication, rate limiting, structured logging, request timeouts, and stronger observability.

## Roadmap

- Add dependency lockfile for fully reproducible installs.
- Add mocked OpenAI Responses API tests.
- Improve out-of-domain answers so unavailable data is rejected more explicitly.
- Add frontend screenshots and a hosted demo link.
- Add structured logging for route choice, tool calls, latency, and fallback reasons.
- Replace remaining frontend `innerHTML` rendering with safer DOM construction.

