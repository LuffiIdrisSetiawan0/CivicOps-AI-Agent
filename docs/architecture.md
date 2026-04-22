# Architecture

## Runtime Flow

```text
User question
  -> FastAPI /api/chat
    -> Router/Supervisor Agent
      -> classify route: general, sql, document, hybrid, guardrail, or unsupported
      -> SQL Data Analyst Agent
        -> read-only SQL templates
        -> SQLite tables
      -> Document/RAG Agent
        -> LlamaIndex + ChromaDB when OpenAI key is configured
        -> lexical retrieval fallback for local/offline mode
      -> Mock API Tool
        -> synthetic flood/network/operational signals
      -> Conversational Agent
        -> GPT-like chat response when OpenAI is configured
      -> Quality Checker Agent
        -> checks evidence, grounding markers, and fallback behavior
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

Chat mode is the default when `OPENAI_API_KEY` is present. It answers general questions like a normal GenAI chatbot, and uses local SQL/RAG/mock API evidence for civic operations questions.

Fast mode is the deterministic local path. It uses routing, read-only SQL templates, cached lexical document retrieval, and mock API signals without calling OpenAI.

Polish mode runs the local grounded answer first, then sends it through one OpenAI Responses API call to improve wording. If OpenAI fails or times out, the fast answer is returned.
