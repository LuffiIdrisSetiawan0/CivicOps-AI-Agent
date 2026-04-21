# Demo Video Script

Target duration: 2-3 minutes.

## 1. Opening

"Saya membangun SatuData Ops Agent, portfolio MVP untuk role AI Engineer LLM-Based Model. Fokusnya adalah multi-agent system yang menggabungkan SQL, dokumen kebijakan, complaint logs, mock API signals, dan evaluasi."

## 2. Architecture

"Di backend saya memakai FastAPI dan Python. Agent dibagi menjadi Router/Supervisor, SQL Data Analyst, Document/RAG Agent, dan Quality Checker. Jika OpenAI API key tersedia, aplikasi memakai Responses API dengan function tools. Jika tidak, fallback deterministic tetap menjaga demo berjalan."

## 3. SQL Demo

Question: "Region dan layanan mana yang memiliki backlog tertinggi?"

Show:

- answer
- SQL preview
- rows
- trace from Router and SQL Agent

## 4. RAG Demo

Question: "Apa kebijakan eskalasi untuk complaint high severity?"

Show:

- answer with policy citation
- retrieved document
- quality check trace

## 5. Hybrid Demo

Question: "Gabungkan backlog dan aturan eskalasi SLA untuk rekomendasi operasi."

Show:

- SQL data
- policy citations
- recommendation
- trace

## 6. Evaluation

Open Evaluation tab and run eval.

"Saya menambahkan 20 golden questions untuk mengecek SQL, RAG, hybrid reasoning, dan guardrail. Target MVP adalah minimal 16 dari 20 passing."

## 7. Closing

"Project ini menunjukkan kemampuan Python, OpenAI SDK, LLM tool calling, SQL analytics, RAG, agent orchestration, guardrails, dan evaluation-driven improvement, sesuai kebutuhan AI Engineer di Nodewave."

