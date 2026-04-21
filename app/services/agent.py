import json
from dataclasses import asdict
from typing import Any

from openai import OpenAI

from app.core.config import get_settings
from app.schemas import ChatResponse, Citation, SQLPreview, ToolTrace
from app.services.mock_api import get_regional_risk_signal
from app.services.rag import RAGService, RetrievalHit
from app.services.sql_tool import SQLResult, analytical_sql_for_question, execute_safe_sql


class SatuDataOpsAgent:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.rag = RAGService()
        self.client = OpenAI(api_key=self.settings.openai_api_key) if self.settings.openai_api_key else None

    def run(self, question: str, include_trace: bool = True) -> ChatResponse:
        if self.client:
            try:
                return self._run_with_openai_tools(question, include_trace=include_trace)
            except Exception as exc:
                fallback = self._run_deterministic(question, include_trace=include_trace)
                fallback.trace.append(
                    ToolTrace(
                        agent="Router/Supervisor Agent",
                        tool="openai_responses_api",
                        input=question,
                        output_preview=f"OpenAI path failed; used deterministic fallback: {exc}",
                        status="fallback",
                    )
                )
                return fallback
        return self._run_deterministic(question, include_trace=include_trace)

    def _run_deterministic(self, question: str, include_trace: bool) -> ChatResponse:
        if self._has_destructive_intent(question):
            traces = [
                ToolTrace(
                    agent="Router/Supervisor Agent",
                    tool="sql_safety_guardrail",
                    input=question,
                    output_preview="Rejected destructive SQL intent before tool execution.",
                    status="blocked",
                ),
                ToolTrace(
                    agent="Quality Checker Agent",
                    tool="validate_answer_grounding",
                    input=question,
                    output_preview="grounded",
                ),
            ]
            return ChatResponse(
                answer=(
                    "Saya menolak menjalankan permintaan destructive SQL seperti DROP, DELETE, "
                    "UPDATE, INSERT, atau ALTER. Demo ini hanya mengizinkan analisis read-only. "
                    "Silakan ajukan pertanyaan analitik, misalnya jumlah layanan, backlog, SLA, "
                    "keluhan, atau anggaran."
                ),
                route="guardrail",
                confidence=0.95,
                citations=[],
                sql=None,
                trace=traces if include_trace else [],
                model="deterministic-fallback",
                used_openai=False,
            )

        route = self._route(question)
        traces: list[ToolTrace] = [
            ToolTrace(
                agent="Router/Supervisor Agent",
                tool="route_question",
                input=question,
                output_preview=route,
            )
        ]

        sql_result: SQLResult | None = None
        if route in {"sql", "hybrid"}:
            sql_query = analytical_sql_for_question(question)
            if sql_query:
                sql_result = execute_safe_sql(sql_query)
                traces.append(
                    ToolTrace(
                        agent="SQL Data Analyst Agent",
                        tool="execute_safe_sql",
                        input=sql_result.query,
                        output_preview=f"{len(sql_result.rows)} rows: {sql_result.rows[:2]}",
                    )
                )

        citations: list[RetrievalHit] = []
        if route in {"document", "hybrid"}:
            citations = self.rag.search(question, top_k=4)
            traces.append(
                ToolTrace(
                    agent="Document/RAG Agent",
                    tool="search_policy_documents",
                    input=question,
                    output_preview=f"{len(citations)} citations found",
                )
            )

        risk_signal = None
        if route == "hybrid" or any(
            keyword in question.lower()
            for keyword in ["risiko", "risk", "cuaca", "banjir", "network", "jaringan"]
        ):
            risk_signal = get_regional_risk_signal(question)
            traces.append(
                ToolTrace(
                    agent="Router/Supervisor Agent",
                    tool="get_mock_regional_signal",
                    input=question,
                    output_preview=str(asdict(risk_signal)),
                )
            )

        answer = self._compose_answer(question, route, sql_result, citations, risk_signal)
        quality = self._quality_check(answer, bool(sql_result), bool(citations))
        traces.append(
            ToolTrace(
                agent="Quality Checker Agent",
                tool="validate_answer_grounding",
                input=question,
                output_preview=quality,
            )
        )

        if not include_trace:
            traces = []

        return ChatResponse(
            answer=answer,
            route=route,
            confidence=0.86 if quality == "grounded" else 0.66,
            citations=[self._citation_from_hit(hit) for hit in citations],
            sql=self._sql_preview(sql_result),
            trace=traces,
            model="deterministic-fallback",
            used_openai=False,
        )

    def _run_with_openai_tools(self, question: str, include_trace: bool) -> ChatResponse:
        if self._has_destructive_intent(question):
            return self._run_deterministic(question, include_trace=include_trace)

        traces: list[ToolTrace] = []
        collected_sql: SQLResult | None = None
        collected_citations: list[RetrievalHit] = []
        route = self._route(question)

        tools = [
            {
                "type": "function",
                "name": "run_sql_analysis",
                "description": "Run a read-only SQL analysis over synthetic Satu Data operations tables.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "intent": {
                            "type": "string",
                            "description": "The analytical question or metric intent to answer.",
                        }
                    },
                    "required": ["intent"],
                    "additionalProperties": False,
                },
            },
            {
                "type": "function",
                "name": "search_policy_documents",
                "description": "Search governance, SLA, budget, and data quality policy documents.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search query for relevant policy context.",
                        }
                    },
                    "required": ["query"],
                    "additionalProperties": False,
                },
            },
            {
                "type": "function",
                "name": "get_mock_regional_signal",
                "description": "Get synthetic regional risk signals such as flood and network status.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "region_or_question": {
                            "type": "string",
                            "description": "Region name or the full user question.",
                        }
                    },
                    "required": ["region_or_question"],
                    "additionalProperties": False,
                },
            },
        ]

        instructions = """
You are SatuData Ops Agent, a portfolio-grade AI engineer demo for regional operations.
Use tools before answering whenever the question touches metrics, policy, complaints, risk, or budgets.
Answer in Indonesian by default. Keep answers concise, cite evidence by table/document/tool name,
separate observed data from recommendations, and do not invent unavailable fields.
"""
        input_items: list[Any] = [{"role": "user", "content": question}]
        final_text = ""

        for _ in range(4):
            response = self.client.responses.create(
                model=self.settings.openai_model,
                instructions=instructions,
                tools=tools,
                input=input_items,
            )
            output_items = list(getattr(response, "output", []) or [])
            tool_calls = [
                item for item in output_items if getattr(item, "type", None) == "function_call"
            ]
            if not tool_calls:
                final_text = getattr(response, "output_text", "") or ""
                break

            input_items.extend(output_items)
            for call in tool_calls:
                name = getattr(call, "name", "")
                args = self._json_args(getattr(call, "arguments", "{}"))
                tool_output, sql_result, citations = self._execute_openai_tool(name, args, question)
                if sql_result:
                    collected_sql = sql_result
                if citations:
                    collected_citations.extend(citations)
                traces.append(
                    ToolTrace(
                        agent=self._agent_for_tool(name),
                        tool=name,
                        input=json.dumps(args, ensure_ascii=False),
                        output_preview=json.dumps(tool_output, ensure_ascii=False)[:500],
                    )
                )
                input_items.append(
                    {
                        "type": "function_call_output",
                        "call_id": call.call_id,
                        "output": json.dumps(tool_output, ensure_ascii=False),
                    }
                )

        if not final_text:
            deterministic = self._run_deterministic(question, include_trace=True)
            final_text = deterministic.answer
            collected_sql = collected_sql or self._result_from_preview(deterministic.sql)
            collected_citations = collected_citations or [
                RetrievalHit(
                    source=item.source,
                    title=item.title,
                    snippet=item.snippet,
                    score=item.score,
                )
                for item in deterministic.citations
            ]

        quality = self._quality_check(final_text, bool(collected_sql), bool(collected_citations))
        traces.append(
            ToolTrace(
                agent="Quality Checker Agent",
                tool="validate_answer_grounding",
                input=question,
                output_preview=quality,
            )
        )

        if not include_trace:
            traces = []

        return ChatResponse(
            answer=final_text,
            route=route,
            confidence=0.9 if quality == "grounded" else 0.72,
            citations=[self._citation_from_hit(hit) for hit in collected_citations[:5]],
            sql=self._sql_preview(collected_sql),
            trace=traces,
            model=self.settings.openai_model,
            used_openai=True,
        )

    def _execute_openai_tool(
        self, name: str, args: dict[str, Any], question: str
    ) -> tuple[dict[str, Any], SQLResult | None, list[RetrievalHit]]:
        if name == "run_sql_analysis":
            intent = str(args.get("intent") or question)
            query = analytical_sql_for_question(intent) or analytical_sql_for_question(question)
            if not query:
                return {"error": "No matching analytical SQL template for this intent."}, None, []
            result = execute_safe_sql(query)
            return {
                "query": result.query,
                "columns": result.columns,
                "rows": result.rows,
                "source": "SQLite tables: monthly_kpis, regions, public_services, complaint_logs, budgets",
            }, result, []
        if name == "search_policy_documents":
            hits = self.rag.search(str(args.get("query") or question), top_k=4)
            return {"citations": [asdict(hit) for hit in hits]}, None, hits
        if name == "get_mock_regional_signal":
            signal = get_regional_risk_signal(str(args.get("region_or_question") or question))
            return asdict(signal), None, []
        return {"error": f"Unknown tool: {name}"}, None, []

    @staticmethod
    def _route(question: str) -> str:
        q = question.lower()
        doc_precedence_phrases = {
            "data warga asli",
            "datanya tidak tersedia",
            "diperbarui",
            "indikator program anggaran yang sehat",
            "menurut playbook",
            "pilot 2025",
            "prioritas layanan pilot",
            "seberapa sering",
        }
        if any(phrase in q for phrase in doc_precedence_phrases):
            return "document"

        sql_terms = {
            "anggaran",
            "backlog",
            "budget",
            "keluhan",
            "kpi",
            "layanan",
            "realisasi",
            "request",
            "service",
            "sla",
            "sql",
        }
        doc_terms = {
            "aturan",
            "dokumen",
            "escalate",
            "eskalasi",
            "kebijakan",
            "policy",
            "prosedur",
            "rekomendasi",
            "sla",
            "tersedia",
        }
        has_sql = any(term in q for term in sql_terms)
        has_doc = any(term in q for term in doc_terms)
        if has_sql and has_doc:
            return "hybrid"
        if has_sql:
            return "sql"
        if has_doc:
            return "document"
        return "hybrid"

    def _compose_answer(
        self,
        question: str,
        route: str,
        sql_result: SQLResult | None,
        citations: list[RetrievalHit],
        risk_signal: Any,
    ) -> str:
        lines = [
            f"Route: {route}. Saya memakai bukti dari data sintetis Satu Data Ops untuk menjawab pertanyaan: \"{question}\".",
        ]
        if sql_result and sql_result.rows:
            lines.append("Temuan data utama:")
            for row in sql_result.rows[:3]:
                summary = ", ".join(f"{key}={value}" for key, value in row.items())
                lines.append(f"- {summary}")
            lines.append(f"Sumber SQL: `{sql_result.query}`")
        elif sql_result:
            lines.append("SQL berhasil dijalankan, tetapi tidak ada baris yang cocok.")

        if citations:
            lines.append("Konteks kebijakan terkait:")
            for hit in citations[:3]:
                lines.append(f"- {hit.title}: {hit.snippet}")

        if risk_signal:
            lines.append(
                "Sinyal operasional mock API: "
                f"{risk_signal.region}, flood_risk={risk_signal.flood_risk}, "
                f"network_status={risk_signal.network_status}. {risk_signal.operational_note}"
            )

        if not sql_result and not citations:
            lines.append(
                "Saya tidak menemukan bukti langsung. Ajukan pertanyaan tentang KPI, backlog, SLA, "
                "keluhan, anggaran, atau kebijakan operasional agar agent bisa memakai tool yang relevan."
            )
        else:
            lines.append(
                "Rekomendasi: validasi region/service prioritas dengan tim data, lalu eskalasikan item "
                "yang memiliki backlog tinggi, SLA lewat batas, atau program delayed."
            )
        return "\n".join(lines)

    @staticmethod
    def _quality_check(answer: str, has_sql: bool, has_citations: bool) -> str:
        answer_lower = answer.lower()
        if "menolak menjalankan permintaan destructive sql" in answer_lower:
            return "grounded"
        has_evidence_word = any(
            marker in answer_lower for marker in ["sumber", "sql", "policy", "kebijakan", "tool"]
        )
        if (has_sql or has_citations) and has_evidence_word:
            return "grounded"
        if not has_sql and not has_citations and "tidak menemukan" in answer_lower:
            return "grounded"
        return "needs_review"

    @staticmethod
    def _citation_from_hit(hit: RetrievalHit) -> Citation:
        return Citation(source=hit.source, title=hit.title, snippet=hit.snippet, score=hit.score)

    @staticmethod
    def _sql_preview(result: SQLResult | None) -> SQLPreview | None:
        if not result:
            return None
        return SQLPreview(query=result.query, columns=result.columns, rows=result.rows[:10])

    @staticmethod
    def _result_from_preview(preview: SQLPreview | None) -> SQLResult | None:
        if not preview:
            return None
        return SQLResult(query=preview.query, columns=preview.columns, rows=preview.rows)

    @staticmethod
    def _json_args(raw: str) -> dict[str, Any]:
        try:
            parsed = json.loads(raw or "{}")
            return parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            return {}

    @staticmethod
    def _agent_for_tool(tool_name: str) -> str:
        return {
            "run_sql_analysis": "SQL Data Analyst Agent",
            "search_policy_documents": "Document/RAG Agent",
            "get_mock_regional_signal": "Router/Supervisor Agent",
        }.get(tool_name, "Router/Supervisor Agent")

    @staticmethod
    def _has_destructive_intent(question: str) -> bool:
        q = f" {question.lower()} "
        return any(
            keyword in q
            for keyword in [
                " drop ",
                " delete ",
                " update ",
                " insert ",
                " alter ",
                " truncate ",
                " hapus table ",
                " ubah table ",
            ]
        )
