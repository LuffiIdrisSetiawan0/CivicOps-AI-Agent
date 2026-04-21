# SatuData Ops Agent

Python-first portfolio MVP for an **AI Engineer (LLM-Based Model)** role. The app demonstrates a multi-agent assistant that can reason over synthetic regional operations data, policy documents, complaint logs, and mock API signals.

## Why This Fits Nodewave

| Job requirement | Evidence in this project |
| --- | --- |
| Python for AI/ML development | FastAPI service, SQL tools, RAG service, evaluation harness |
| Multi-agent LLM systems | Router/Supervisor, SQL Analyst, Document/RAG Agent, Quality Checker |
| SQL, data marts, warehouses | SQLite operational schema with KPI, complaints, budget, region, and service tables |
| Unstructured data | Policy documents indexed for retrieval and cited in answers |
| OpenAI SDK | Responses API integration with function tools when `OPENAI_API_KEY` is configured |
| RAG and hybrid search | LlamaIndex + ChromaDB path with lexical fallback for local demos |
| Evaluations | 20 golden questions with pass-rate target of 16/20 |
| Production-ready prototype | API endpoints, dashboard, guardrails, docs, deployment config |

## Features

- Ask operational questions in Indonesian or English.
- Route questions to SQL, policy retrieval, mock API signals, or hybrid reasoning.
- Preview the SQL query and rows used by the answer.
- Inspect policy citations and agent/tool trace.
- Run a golden-question evaluation from the UI or API.
- Run without an API key in deterministic fallback mode.

## Architecture

```text
Browser Dashboard
  -> FastAPI
    -> Router/Supervisor Agent
      -> SQL Data Analyst Agent -> SQLite synthetic Satu Data tables
      -> Document/RAG Agent -> LlamaIndex + ChromaDB or lexical fallback
      -> Mock API Tool -> regional risk signals
      -> Quality Checker Agent -> grounded answer checks
```

## Quick Start

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
uvicorn app.main:app --reload
```

Open `http://127.0.0.1:8000`.

Optional OpenAI mode:

```powershell
$env:OPENAI_API_KEY="your_key_here"
$env:OPENAI_MODEL="gpt-5-mini"
uvicorn app.main:app --reload
```

Without `OPENAI_API_KEY`, the app still runs using deterministic routing, SQL templates, lexical document retrieval, and mock risk signals.

## API

- `GET /api/health`
- `POST /api/chat`
- `GET /api/datasets/preview`
- `POST /api/eval/run`

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

More scenarios are in [docs/demo_questions.md](docs/demo_questions.md).

## Evaluation

Run from the dashboard or:

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/api/eval/run
```

Target: at least **16/20** golden questions passing.

## Deployment

This repo includes `Dockerfile` and `render.yaml` for a simple FastAPI deployment. Set these environment variables on the host:

- `OPENAI_API_KEY`
- `OPENAI_MODEL`
- `EMBEDDING_MODEL`
- `DATABASE_URL`
- `CHROMA_PATH`

SQLite is acceptable for the MVP. For a longer-running public demo, use a persistent disk or managed Postgres.

## Notes

- All data is synthetic and safe to publish.
- The SQL guardrail blocks destructive statements and only allows read-only analysis.
- No fine-tuning is included in v1; reliability is shown through retrieval, guardrails, and evaluation.

