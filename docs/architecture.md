# Architecture

## Runtime Flow

```text
User question
  -> FastAPI /api/chat
    -> Router/Supervisor Agent
      -> classify route: sql, document, hybrid, guardrail
      -> SQL Data Analyst Agent
        -> read-only SQL templates
        -> SQLite tables
      -> Document/RAG Agent
        -> LlamaIndex + ChromaDB when OpenAI key is configured
        -> lexical retrieval fallback for local/offline mode
      -> Mock API Tool
        -> synthetic flood/network/operational signals
      -> Quality Checker Agent
        -> checks evidence and grounding markers
    -> structured response for dashboard
```

## Data Sources

- `regions`: synthetic regional metadata and population.
- `public_services`: services, categories, channels, and SLA.
- `monthly_kpis`: requests, completion, resolution time, satisfaction, backlog.
- `complaint_logs`: ticket topics, severity, sentiment, channels.
- `budgets`: allocation, realization, vendor, program status.
- `data/policies`: governance, complaint SLA, budget monitoring, data quality policies.

## Agent Roles

- **Router/Supervisor Agent** chooses SQL, document, hybrid, or guardrail route.
- **SQL Data Analyst Agent** runs validated read-only SQL for structured metrics.
- **Document/RAG Agent** retrieves policy evidence and citations.
- **Quality Checker Agent** checks whether the answer is evidence-backed.

## OpenAI Integration

When `OPENAI_API_KEY` is present, `SatuDataOpsAgent` uses the OpenAI Responses API with function tools:

- `run_sql_analysis`
- `search_policy_documents`
- `get_mock_regional_signal`

When no key is present, deterministic fallback mode preserves the same public response shape.

