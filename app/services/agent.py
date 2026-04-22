import json
import time
from dataclasses import asdict
from pathlib import Path
from typing import Literal

from openai import OpenAI

from app.core.config import get_settings
from app.schemas import ChatHistoryMessage, ChatResponse, Citation, SQLPreview, ToolTrace
from app.services.mock_api import RegionalRiskSignal, get_regional_risk_signal
from app.services.rag import RAGService, RetrievalHit
from app.services.sql_tool import (
    SQLResult,
    analytical_sql_for_question,
    dataset_preview,
    execute_safe_sql,
)

AnswerMode = Literal["chat", "fast", "polish"]

AGENT_SYSTEM_PROMPT = """
You are an Indonesian conversational analyst/copilot for a SatuData operations demo.

Core behavior:
- Answer only the user's exact intent. If the question is narrow, answer narrowly.
- Strict rule: if a section is not directly answering the question, exclude it.
- Use only the provided draft answer, data rows, source snippets, or explicitly known app scope. Do not invent tables, policies, metrics, dates, regions, or causal explanations.
- Do not say you checked data, queried SQL, searched policy, or reviewed sources unless the prompt includes explicit data rows or source snippets for that claim.
- Separate facts, limitations, and recommendations. Label inference as inference and recommendation as recommendation when both appear.
- Do not include rules, limitations, escalation, recommendations, caveats, or extra context unless the user explicitly asks for them or they are required to answer safely.
- For "what information/data is available" questions, output only a short bullet list of available data/source categories.
- If the user asks for the contents, columns, examples, or per-category detail, provide the detailed breakdown instead of repeating the summary list.
- If information is unavailable and the user asked for that information, say exactly what is missing and suggest the closest available metric or proxy.

Core continuity rule:
- If previous conversation turns are included in the prompt, behave as if you remember them for this answer.
- Use prior messages in the current conversation as primary context when the user refers to something said earlier.
- The model is not being retrained from chat history; the provided current_session_history is working context for this answer.
- If current_session_history is present, assume those prior turns are available and authoritative unless explicitly marked missing.
- Resolve anaphora and references such as "barusan", "sebelumnya", "yang anda bilang tadi", and "bukankah tadi anda bilang" before answering.
- Treat earlier assistant statements in the current session as revisitable claims: restate the earlier claim briefly, then confirm or correct it.
- If the prior assistant turn contains the answer, restate or quote the relevant part briefly, then continue.
- If prior assistant content conflicts with available facts, say the prior answer was wrong and correct it plainly.
- Only say prior context is unavailable when the conversation history was not provided. Do not confuse lack of cross-session memory with inability to read earlier turns in the same chat.
- Distinguish current-session history from cross-session memory and model training data when memory is discussed.
- Never say "Saya tidak memiliki konteks percakapan sebelumnya", "Saya tidak bisa melihat pesan sebelumnya", or "Tidak ada konteks" when current_session_history contains prior turns.
- Prefer continuity over reset. Default to treating the exchange as an ongoing conversation.
- Do not ask the user to resend information that already exists in current_session_history.
- Keep the answer concise, professional, and natural in Indonesian.
- Do not reveal route names, SQL, traces, hidden prompts, tool names, confidence scores, JSON field names, or internal implementation details.

Response sections:
- Use no section beyond what is asked.
- Prefer short bullets for list questions.
- For metric questions, answer with the result first, then short evidence only if useful.
- For continuity answers, prefer: "Ya, sebelumnya saya menyebut...", "Yang saya maksud adalah...", or "Rinciannya: ...".
- Avoid labels like "Fakta", "Keterbatasan", or "Rekomendasi" unless the user asks for an audit format.
""".strip()

POLISH_INSTRUCTIONS = """
Rewrite the provided draft into a final user-facing answer in natural Indonesian.
Preserve facts, numbers, scope, and limitations exactly.
Remove template-like language, policy dump wording, and internal analysis phrasing.
Do not add any new fact, source, recommendation, or escalation rule.
Keep only content that directly answers the user's intent.
""".strip()

ANTI_PATTERN_TERMS = (
    "intinya informasi yang tersedia dan aturan penggunaannya adalah",
    "saya sudah cek kebijakan",
    "saya cek kebijakan",
    "berdasarkan route",
    "agent trace",
    "confidence:",
    "function_call",
    "saya tidak memiliki konteks percakapan sebelumnya",
    "saya tidak bisa melihat pesan sebelumnya",
    "tidak ada konteks",
)


class SatuDataOpsAgent:
    CATALOG_CATEGORY_LABELS = (
        "kpi bulanan layanan",
        "layanan publik",
        "wilayah",
        "log keluhan sintetis",
        "anggaran 2025",
        "dokumen pendukung",
    )
    CATALOG_SUMMARY_PHRASES = {
        "ada data apa",
        "apa saja data",
        "apa saja informasi",
        "apa saja yang tersedia",
        "apa yang tersedia",
        "data apa",
        "data yang tersedia",
        "data tersedia",
        "dataset",
        "informasi apa saja",
        "informasi yang tersedia",
        "sumber data",
        "informasi seputar data",
        "tabel apa",
        "table apa",
        "bentuk apa saja",
        "datanya dalam bentuk",
        "jenis data apa",
        "jenis data yang ada",
        "kategori data apa",
        "bentuk data",
    }
    CATALOG_DETAIL_PHRASES = {
        "isi data",
        "isi datanya",
        "rincian data",
        "detail data",
        "struktur data",
        "skema data",
        "kolom apa",
        "field apa",
        "atribut apa",
        "contoh data",
        "contoh isinya",
        "per jenis data",
        "tiap jenis data",
        "masing-masing data",
        "setiap jenis data",
        "isi tiap",
        "isi masing-masing",
    }
    CATALOG_FOLLOWUP_TERMS = {
        "isi",
        "kolom",
        "field",
        "atribut",
        "detail",
        "rincian",
        "contoh",
        "tiap",
        "setiap",
        "masing-masing",
        "jenis",
        "struktur",
        "skema",
    }
    SQL_TERMS = {
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
        "satisfaction",
        "kepuasan",
        "skor",
        "complaint",
        "sentiment",
        "sentimen",
        "topik",
        "resolution",
        "penyelesaian",
        "terlambat",
    }
    DOC_TERMS = {
        "aturan",
        "dokumen",
        "escalate",
        "eskalasi",
        "kebijakan",
        "policy",
        "playbook",
        "prosedur",
        "rekomendasi",
        "tersedia",
        "diperbarui",
        "prioritas",
        "pilot",
        "data warga",
        "data asli",
    }
    RISK_TERMS = {"risiko", "risk", "cuaca", "banjir", "network", "jaringan", "intermittent"}
    REGION_TERMS = {"palangka", "kapuas", "kotawaringin", "barito", "murung"}
    DOC_PRECEDENCE_PHRASES = {
        "complaint high severity",
        "high severity",
        "data warga asli",
        "datanya tidak tersedia",
        "diperbarui",
        "kebijakan eskalasi",
        "indikator program anggaran yang sehat",
        "menurut playbook",
        "pilot 2025",
        "prioritas layanan pilot",
        "seberapa sering",
    }

    def __init__(self) -> None:
        self.settings = get_settings()
        self.rag = RAGService()
        self._openai_client: OpenAI | None = None

    def run(
        self,
        question: str,
        include_trace: bool = True,
        answer_mode: AnswerMode = "chat",
        conversation_history: list[ChatHistoryMessage | dict] | None = None,
    ) -> ChatResponse:
        started = time.perf_counter()
        mode = self._normalize_answer_mode(answer_mode)
        history = self._normalize_conversation_history(conversation_history)
        response = self._run_fast(question, answer_mode=mode, conversation_history=history)

        if mode == "chat":
            response = self._chat_response(question, response, history)
        elif mode == "polish":
            response = self._polish_response(question, response, history)

        response.latency_ms = self._elapsed_ms(started)
        if not include_trace:
            response.trace = []
        return response

    def _run_fast(
        self,
        question: str,
        answer_mode: AnswerMode,
        conversation_history: list[ChatHistoryMessage],
    ) -> ChatResponse:
        traces: list[ToolTrace] = []

        if self._has_destructive_intent(question):
            traces.append(
                ToolTrace(
                    agent="Router/Supervisor Agent",
                    tool="sql_safety_guardrail",
                    input=question,
                    output_preview="Rejected destructive SQL intent before tool execution.",
                    status="blocked",
                    duration_ms=0.0,
                )
            )
            answer = self._compose_guardrail_answer()
            traces.append(self._quality_trace(question, answer, has_sql=False, has_citations=False))
            return ChatResponse(
                answer=answer,
                route="guardrail",
                confidence=0.95,
                citations=[],
                sql=None,
                trace=traces,
                model="deterministic-fast",
                used_openai=False,
                answer_mode="fast" if answer_mode == "polish" else answer_mode,
            )

        if self._is_context_reference_question(question):
            context_started = time.perf_counter()
            answer = self._compose_context_reference_answer(question, conversation_history)
            traces.append(
                ToolTrace(
                    agent="Conversational Agent",
                    tool="read_current_session_history",
                    input=question,
                    output_preview="Answered by revisiting current-session conversation history.",
                    duration_ms=self._elapsed_ms(context_started),
                )
            )
            traces.append(
                self._quality_trace(
                    question,
                    answer,
                    has_sql=False,
                    has_citations=False,
                    quality="grounded",
                )
            )
            return ChatResponse(
                answer=answer,
                route="conversation",
                confidence=0.88 if conversation_history else 0.52,
                citations=[],
                sql=None,
                trace=traces,
                model="deterministic-fast",
                used_openai=False,
                answer_mode="fast" if answer_mode == "polish" else answer_mode,
            )

        if self._is_catalog_detail_question(question, conversation_history):
            catalog_started = time.perf_counter()
            answer = self._compose_catalog_detail_answer()
            traces.append(
                ToolTrace(
                    agent="Router/Supervisor Agent",
                    tool="answer_data_catalog_detail",
                    input=question,
                    output_preview="Returned a detailed breakdown of available demo data.",
                    duration_ms=self._elapsed_ms(catalog_started),
                )
            )
            traces.append(
                self._quality_trace(
                    question,
                    answer,
                    has_sql=False,
                    has_citations=False,
                    quality="grounded",
                )
            )
            return ChatResponse(
                answer=answer,
                route="catalog",
                confidence=0.93,
                citations=[],
                sql=None,
                trace=traces,
                model="deterministic-fast",
                used_openai=False,
                answer_mode="fast" if answer_mode == "polish" else answer_mode,
            )

        if self._is_catalog_question(question):
            catalog_started = time.perf_counter()
            answer = self._compose_catalog_answer()
            traces.append(
                ToolTrace(
                    agent="Router/Supervisor Agent",
                    tool="answer_data_catalog",
                    input=question,
                    output_preview="Returned a user-facing summary of available demo data.",
                    duration_ms=self._elapsed_ms(catalog_started),
                )
            )
            traces.append(
                self._quality_trace(
                    question,
                    answer,
                    has_sql=False,
                    has_citations=False,
                    quality="grounded",
                )
            )
            return ChatResponse(
                answer=answer,
                route="catalog",
                confidence=0.9,
                citations=[],
                sql=None,
                trace=traces,
                model="deterministic-fast",
                used_openai=False,
                answer_mode="fast" if answer_mode == "polish" else answer_mode,
            )

        route_started = time.perf_counter()
        route = self._route(question)
        traces.append(
            ToolTrace(
                agent="Router/Supervisor Agent",
                tool="route_question",
                input=question,
                output_preview=route,
                duration_ms=self._elapsed_ms(route_started),
            )
        )

        if route == "unsupported":
            answer = self._compose_unavailable_answer(question)
            traces.append(self._quality_trace(question, answer, has_sql=False, has_citations=False))
            return ChatResponse(
                answer=answer,
                route=route,
                confidence=0.42,
                citations=[],
                sql=None,
                trace=traces,
                model="deterministic-fast",
                used_openai=False,
                answer_mode="fast" if answer_mode == "polish" else answer_mode,
            )

        sql_result: SQLResult | None = None
        sql_query = analytical_sql_for_question(question) if route in {"sql", "hybrid"} else None
        if route in {"sql", "hybrid"}:
            sql_started = time.perf_counter()
            if sql_query:
                sql_result = execute_safe_sql(sql_query)
                traces.append(
                    ToolTrace(
                        agent="SQL Data Analyst Agent",
                        tool="execute_safe_sql",
                        input=sql_result.query,
                        output_preview=f"{len(sql_result.rows)} rows: {sql_result.rows[:2]}",
                        duration_ms=self._elapsed_ms(sql_started),
                    )
                )
            elif self._has_sql_intent(question.lower()):
                traces.append(
                    ToolTrace(
                        agent="SQL Data Analyst Agent",
                        tool="select_sql_template",
                        input=question,
                        output_preview="No matching analytical SQL template.",
                        status="skipped",
                        duration_ms=self._elapsed_ms(sql_started),
                    )
                )

        citations: list[RetrievalHit] = []
        if route in {"document", "hybrid"}:
            rag_started = time.perf_counter()
            citations = self.rag.search(question, top_k=4)
            traces.append(
                ToolTrace(
                    agent="Document/RAG Agent",
                    tool="search_policy_documents",
                    input=question,
                    output_preview=f"{len(citations)} citations found",
                    duration_ms=self._elapsed_ms(rag_started),
                )
            )

        risk_signal: RegionalRiskSignal | None = None
        if route == "hybrid" or self._has_risk_intent(question.lower()):
            api_started = time.perf_counter()
            risk_signal = get_regional_risk_signal(question)
            traces.append(
                ToolTrace(
                    agent="Router/Supervisor Agent",
                    tool="get_mock_regional_signal",
                    input=question,
                    output_preview=json.dumps(asdict(risk_signal), ensure_ascii=False),
                    duration_ms=self._elapsed_ms(api_started),
                )
            )

        answer = self._compose_answer(question, route, sql_result, citations, risk_signal)
        quality = self._quality_check(answer, bool(sql_result), bool(citations), bool(risk_signal))
        traces.append(
            self._quality_trace(
                question,
                answer,
                bool(sql_result),
                bool(citations),
                quality,
                bool(risk_signal),
            )
        )

        return ChatResponse(
            answer=answer,
            route=route,
            confidence=self._confidence_for(route, quality, sql_result, citations),
            citations=[self._citation_from_hit(hit) for hit in citations],
            sql=self._sql_preview(sql_result),
            trace=traces,
            model="deterministic-fast",
            used_openai=False,
            answer_mode="fast" if answer_mode == "polish" else answer_mode,
        )

    def _chat_response(
        self,
        question: str,
        response: ChatResponse,
        conversation_history: list[ChatHistoryMessage],
    ) -> ChatResponse:
        chat_started = time.perf_counter()

        if response.route in {"sql", "document", "hybrid"} and not (response.sql or response.citations):
            response.trace.append(
                ToolTrace(
                    agent="Conversational Agent",
                    tool="openai_chat",
                    input=question,
                    output_preview=(
                        "Retained the local answer because no SQL rows or citations were available "
                        "for a safe chat rewrite."
                    ),
                    status="fallback",
                    duration_ms=self._elapsed_ms(chat_started),
                )
            )
            response.answer_mode = "fast"
            return response

        client = self._get_openai_client()
        if client is None or response.route == "guardrail":
            if response.route != "guardrail":
                response.trace.append(
                    ToolTrace(
                        agent="Conversational Agent",
                        tool="openai_chat",
                        input=question,
                        output_preview="OpenAI API key is not configured; returned local answer.",
                        status="fallback",
                        duration_ms=self._elapsed_ms(chat_started),
                    )
                )
                response.answer_mode = "fast"
            return response

        try:
            prompt = self._chat_prompt(question, response, conversation_history)
            result = client.responses.create(
                model=self.settings.openai_model,
                instructions=AGENT_SYSTEM_PROMPT,
                input=[{"role": "user", "content": prompt}],
            )
            answer = self._sanitize_chat_answer((getattr(result, "output_text", "") or "").strip())
            if not answer:
                raise ValueError("OpenAI chat returned empty text.")
            response.answer = answer
            response.used_openai = True
            response.model = self.settings.openai_model
            response.confidence = self._chat_confidence(response)
            if response.route == "unsupported":
                response.route = "general"
                response.confidence = 0.78
            response.trace.append(
                ToolTrace(
                    agent="Conversational Agent",
                    tool="openai_chat",
                    input=question,
                    output_preview="Generated a natural chat response with OpenAI.",
                    duration_ms=self._elapsed_ms(chat_started),
                )
            )
        except Exception as exc:
            response.trace.append(
                ToolTrace(
                    agent="Conversational Agent",
                    tool="openai_chat",
                    input=question,
                    output_preview=f"OpenAI chat failed; returned local answer: {exc}",
                    status="fallback",
                    duration_ms=self._elapsed_ms(chat_started),
                )
            )
            if response.route == "unsupported":
                response.answer = self._compose_general_fallback_answer(question)
                response.route = "general"
                response.confidence = 0.52
        return response

    def _polish_response(
        self,
        question: str,
        response: ChatResponse,
        conversation_history: list[ChatHistoryMessage],
    ) -> ChatResponse:
        polish_started = time.perf_counter()
        response.answer_mode = "polish"
        client = self._get_openai_client()
        if client is None:
            response.trace.append(
                ToolTrace(
                    agent="Quality Checker Agent",
                    tool="openai_polish",
                    input=question,
                    output_preview="OpenAI API key is not configured; returned fast answer.",
                    status="fallback",
                    duration_ms=self._elapsed_ms(polish_started),
                )
            )
            return response

        prompt = self._polish_prompt(question, response, conversation_history)
        try:
            result = client.responses.create(
                model=self.settings.openai_model,
                instructions=f"{AGENT_SYSTEM_PROMPT}\n\n{POLISH_INSTRUCTIONS}",
                input=[{"role": "user", "content": prompt}],
            )
            polished = (getattr(result, "output_text", "") or "").strip()
            polished = self._sanitize_chat_answer(polished)
            if not polished:
                raise ValueError("OpenAI polish returned empty text.")
            response.answer = polished
            response.used_openai = True
            response.model = self.settings.openai_model
            response.confidence = min(round(response.confidence + 0.03, 2), 0.95)
            response.trace.append(
                ToolTrace(
                    agent="Quality Checker Agent",
                    tool="openai_polish",
                    input=question,
                    output_preview="Answer polished with one OpenAI Responses API call.",
                    duration_ms=self._elapsed_ms(polish_started),
                )
            )
        except Exception as exc:
            response.trace.append(
                ToolTrace(
                    agent="Quality Checker Agent",
                    tool="openai_polish",
                    input=question,
                    output_preview=f"OpenAI polish failed; returned fast answer: {exc}",
                    status="fallback",
                    duration_ms=self._elapsed_ms(polish_started),
                )
            )
        return response

    def _get_openai_client(self) -> OpenAI | None:
        if not self.settings.openai_api_key:
            return None
        if self._openai_client is None:
            self._openai_client = OpenAI(
                api_key=self.settings.openai_api_key,
                timeout=30.0,
                max_retries=0,
            )
        return self._openai_client

    @classmethod
    def _route(cls, question: str) -> str:
        q = question.lower()
        has_sql = cls._has_sql_intent(q)
        has_doc = cls._has_doc_intent(q)
        has_risk = cls._has_risk_intent(q)
        has_region = cls._mentions_known_region(q)

        if not any([has_sql, has_doc, has_risk, has_region]):
            return "unsupported"
        if any(phrase in q for phrase in cls.DOC_PRECEDENCE_PHRASES):
            return "document"
        if has_sql and has_risk and not has_doc and not has_region:
            if any(term in q for term in ["anggaran", "budget", "realisasi", "spending"]):
                return "sql"
            return "hybrid"
        if has_sql and (has_doc or has_risk or has_region):
            return "hybrid"
        if has_doc and (has_risk or has_region):
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
        risk_signal: RegionalRiskSignal | None,
    ) -> str:
        findings = self._findings(question, sql_result, citations, risk_signal)
        recommendations = self._recommendations(sql_result, citations, risk_signal)
        intro = self._summary_for(question, route, sql_result, citations, risk_signal)

        lines = [intro]
        if findings:
            lines.extend(["", "Fakta yang tersedia:"])
            lines.extend(findings[:4])
        if recommendations:
            lines.extend(["", "Rekomendasi:"])
            lines.extend(recommendations[:3])
        return "\n".join(lines)

    @staticmethod
    def _compose_guardrail_answer() -> str:
        return "\n".join(
            [
                "Saya tidak bisa membantu menjalankan atau mensimulasikan perintah yang mengubah atau menghapus data.",
                "",
                "Untuk demo ini, saya hanya bisa membantu analisis read-only. Coba ajukan pertanyaan seperti jumlah layanan, backlog tertinggi, SLA yang melewati batas, keluhan prioritas, atau risiko anggaran.",
            ]
        )

    @staticmethod
    def _compose_unavailable_answer(question: str) -> str:
        return "\n".join(
            [
                "Data tidak tersedia untuk menjawab pertanyaan itu dari dataset demo yang sedang saya gunakan.",
                "",
                f"Pertanyaannya: {question}",
                "Saat ini saya bisa membantu dengan data KPI layanan publik, backlog, SLA, keluhan, anggaran, kebijakan operasional, dan risiko wilayah.",
                "",
                "Metrik terdekat yang bisa dipakai adalah backlog layanan, realisasi anggaran, layanan yang melewati SLA, topik keluhan, atau risiko operasional per wilayah.",
            ]
        )

    @staticmethod
    def _compose_catalog_answer() -> str:
        return "\n".join(
            [
                "- KPI bulanan layanan: request, selesai, backlog, rata-rata waktu penyelesaian, dan skor kepuasan.",
                "- Layanan publik: KTP Elektronik, Kartu Keluarga, Rujukan Kesehatan, dan Laporan Jalan Rusak.",
                "- Wilayah: Palangka Raya, Kotawaringin Barat, Kapuas, Barito Utara, dan Murung Raya.",
                "- Log keluhan sintetis: topik, severity, channel, sentiment, dan ringkasan pesan.",
                "- Anggaran 2025: alokasi, realisasi, vendor, dan status program.",
                "- Dokumen pendukung: tata kelola Satu Data, SLA keluhan, monitoring anggaran, dan kualitas data.",
            ]
        )

    def _compose_catalog_detail_answer(self) -> str:
        preview = dataset_preview()
        policy_titles_list = self._policy_document_titles()
        service_names = ", ".join(
            row["name"] for row in preview.get("public_services", {}).get("sample_rows", [])
        )
        region_names = ", ".join(
            row["name"] for row in preview.get("regions", {}).get("sample_rows", [])
        )
        policy_titles = ", ".join(policy_titles_list)

        return "\n".join(
            [
                (
                    "- KPI bulanan layanan (`monthly_kpis`, "
                    f"{preview.get('monthly_kpis', {}).get('row_count', 0)} baris): "
                    "kolom utamanya `month`, `request_count`, `completed_count`, "
                    "`backlog_count`, `avg_resolution_days`, `satisfaction_score`, "
                    "serta relasi `region_id` dan `service_id`."
                ),
                (
                    "- Layanan publik (`public_services`, "
                    f"{preview.get('public_services', {}).get('row_count', 0)} baris): "
                    "kolomnya `service_code`, `name`, `category`, `channel`, `sla_days`. "
                    f"Isinya: {service_names}."
                ),
                (
                    "- Wilayah (`regions`, "
                    f"{preview.get('regions', {}).get('row_count', 0)} baris): "
                    "kolomnya `code`, `name`, `province`, `type`, `population`. "
                    f"Wilayah yang ada: {region_names}."
                ),
                (
                    "- Log keluhan sintetis (`complaint_logs`, "
                    f"{preview.get('complaint_logs', {}).get('row_count', 0)} baris): "
                    "kolom utamanya `ticket_id`, `month`, `channel`, `severity`, `topic`, "
                    "`sentiment`, `message`, serta relasi `region_id` dan `service_id`."
                ),
                (
                    "- Anggaran 2025 (`budgets`, "
                    f"{preview.get('budgets', {}).get('row_count', 0)} baris): "
                    "kolomnya `year`, `allocated_billion_idr`, `spent_billion_idr`, `vendor`, "
                    "`program_status`, serta relasi `region_id` dan `service_id`."
                ),
                (
                    "- Dokumen pendukung (`data/policies`, "
                    f"{len(policy_titles_list)} file): "
                    f"{policy_titles}."
                ),
            ]
        )

    @staticmethod
    def _summary_for(
        question: str,
        route: str,
        sql_result: SQLResult | None,
        citations: list[RetrievalHit],
        risk_signal: RegionalRiskSignal | None,
    ) -> str:
        if sql_result and citations:
            return "Berdasarkan data operasional dan dokumen pendukung yang tersedia, prioritasnya adalah:"
        if sql_result:
            return "Berdasarkan data operasional yang tersedia, prioritasnya adalah:"
        if citations and risk_signal:
            return "Berdasarkan dokumen pendukung dan sinyal risiko wilayah yang tersedia:"
        if citations:
            return "Berdasarkan dokumen pendukung yang tersedia:"
        if risk_signal:
            return "Berdasarkan sinyal risiko wilayah yang tersedia:"
        return "Saya belum menemukan sumber lokal yang cukup untuk menjawab pertanyaan itu secara spesifik."

    def _findings(
        self,
        question: str,
        sql_result: SQLResult | None,
        citations: list[RetrievalHit],
        risk_signal: RegionalRiskSignal | None,
    ) -> list[str]:
        lines: list[str] = []
        if sql_result and sql_result.rows:
            for row in sql_result.rows[:3]:
                lines.append(f"- {self._format_row(row)}")
        elif sql_result:
            lines.append("- Tidak ada baris data yang cocok dengan pertanyaan ini.")

        seen_policy_lines: set[str] = set()
        for hit in citations:
            line = f"- {self._format_policy_hit(hit, question)}"
            if line in seen_policy_lines:
                continue
            seen_policy_lines.add(line)
            lines.append(line)
            if len(seen_policy_lines) >= 2:
                break

        if risk_signal:
            lines.append(
                "- "
                f"Di {risk_signal.region}, risiko banjir berada pada level {risk_signal.flood_risk} "
                f"dan kondisi jaringan {risk_signal.network_status}. {risk_signal.operational_note}"
            )

        return lines

    @staticmethod
    def _format_policy_hit(hit: RetrievalHit, question: str = "") -> str:
        q = question.lower()
        snippet = " ".join(hit.snippet.split())
        snippet_lower = snippet.lower()

        def sourced(text: str) -> str:
            return f"{text} (Sumber: {hit.title})"

        if "destructive sql" in snippet_lower and "personally identifiable" in snippet_lower:
            return sourced(
                "Demo ini memakai data synthetic dan tidak berisi PII atau data warga asli. "
                "Permintaan SQL yang mengubah atau menghapus data juga harus ditolak."
            )
        if "when a question cannot be answered" in snippet_lower:
            return sourced(
                "Kalau data tidak tersedia dari tabel SQL, dokumen, log keluhan, atau mock API, "
                "jawaban harus menyebutkan bagian yang belum ada dan menawarkan metrik terdekat yang masih bisa dipakai."
            )
        if "quality checks should verify" in snippet_lower:
            return sourced(
                "Jawaban perlu tetap berbasis bukti, tidak melebih-lebihkan sebab-akibat, "
                "dan membedakan angka metrik dari rekomendasi kebijakan."
            )
        if "priority services for the 2025 pilot" in snippet_lower:
            if any(term in q for term in ["eskalasi", "escalation", "high severity", "complaint"]):
                return sourced(
                    "Eskalasi lintas instansi diperlukan jika layanan melewati SLA dua bulan berturut-turut atau keluhan high severity meningkat."
                )
            return sourced(
                "Prioritas layanan pilot 2025 adalah KTP Elektronik, Kartu Keluarga, Rujukan Kesehatan, dan Laporan Jalan Rusak. "
                "Eskalasi lintas instansi diperlukan jika layanan melewati SLA dua bulan berturut-turut atau keluhan high severity meningkat."
            )
        if "high-severity complaints" in snippet_lower:
            return sourced(
                "Keluhan high severity perlu respons pertama dalam satu working day. "
                "Keluhan medium diberi respons awal dalam tiga working days, sedangkan low severity bisa dikelompokkan mingguan."
            )
        if "escalate to the regional operations lead" in snippet_lower:
            return sourced(
                "Eskalasi ke regional operations lead jika backlog melebihi sepuluh tiket untuk layanan yang sama dalam satu bulan. "
                "Eskalasi ke tim data diperlukan jika keluhan berulang menyebut mismatch data, duplikasi identitas, status dokumen hilang, atau sinkronisasi usang."
            )
        if "recommended mitigation" in snippet_lower:
            return sourced(
                "Mitigasi yang disarankan adalah menerbitkan update status, memastikan kanal layanan yang terdampak, "
                "dan membandingkan topik keluhan dengan tren KPI bulanan sebelum memberi aksi ke vendor atau instansi."
            )
        if "budget monitoring compares" in snippet_lower:
            return sourced(
                "Monitoring budget membandingkan alokasi, realisasi belanja, backlog layanan, dan skor kepuasan. "
                "Program yang delayed perlu rencana pemulihan singkat dengan owner, target tanggal, dan dependensi."
            )
        if "healthy programs typically show" in snippet_lower:
            return sourced(
                "Program yang sehat biasanya punya realisasi di atas 60 persen pada pertengahan tahun, "
                "backlog stabil di bawah sepuluh item per pasangan wilayah-layanan, dan satisfaction score di atas 3.8."
            )
        if "for executive reporting" in snippet_lower:
            return sourced(
                "Untuk laporan eksekutif, rangkum tiga risiko teratas, wilayah terdampak, kategori layanan, dan langkah berikutnya. "
                "Jangan menambahkan data pengadaan yang tidak ada di tabel budget."
            )
        if "data freshness rules" in snippet_lower:
            return sourced(
                "Aturan freshness datanya: tabel KPI diperbarui monthly, complaint log diperbarui daily, "
                "dan realisasi budget diperbarui pada akhir setiap bulan."
            )
        if "satudata ops consolidates" in snippet_lower:
            return sourced(
                "SatuData Ops menggabungkan data demografi, layanan publik, keluhan, dan budget untuk membantu keputusan operasional daerah."
            )

        return f"{hit.title}: {snippet}"

    @staticmethod
    def _evidence(
        sql_result: SQLResult | None,
        citations: list[RetrievalHit],
        risk_signal: RegionalRiskSignal | None,
    ) -> list[str]:
        evidence: list[str] = []
        if sql_result:
            evidence.append(
                "- SQL tables: monthly_kpis, regions, public_services, complaint_logs, budgets."
            )
        if citations:
            titles = ", ".join(dict.fromkeys(hit.title for hit in citations[:4]))
            evidence.append(f"- Policy documents: {titles}.")
        if risk_signal:
            evidence.append("- Mock API: synthetic regional flood and network signal.")
        return evidence or ["- No matching evidence source found."]

    @staticmethod
    def _recommendations(
        sql_result: SQLResult | None,
        citations: list[RetrievalHit],
        risk_signal: RegionalRiskSignal | None,
    ) -> list[str]:
        if not any([sql_result, citations, risk_signal]):
            return ["- Persempit pertanyaan ke KPI, backlog, SLA, keluhan, anggaran, kebijakan, atau risiko wilayah."]
        if citations and not sql_result and not risk_signal:
            return []

        recommendations = [
            "- Prioritaskan kombinasi wilayah dan layanan yang backlog-nya paling tinggi atau status programnya tertunda.",
            "- Validasi penanggung jawab tindak lanjut sebelum melakukan eskalasi operasional.",
        ]
        if citations:
            recommendations.append("- Cocokkan tindakan dengan aturan eskalasi dan kebijakan kualitas data yang relevan.")
        if risk_signal:
            recommendations.append("- Sesuaikan rencana operasi dengan kondisi jaringan dan risiko wilayah.")
        return recommendations[:3]

    @staticmethod
    def _format_row(row: dict) -> str:
        if {"region", "service", "backlog_count", "month"}.issubset(row):
            return (
                f"{row['region']} - {row['service']} mencatat backlog {row['backlog_count']} "
                f"pada {row['month']}, dengan {row.get('completed_count')} dari "
                f"{row.get('request_count')} permintaan selesai dan skor kepuasan "
                f"{row.get('satisfaction_score')}."
            )
        if {"region", "service", "spend_pct", "program_status"}.issubset(row):
            return (
                f"{row['region']} - {row['service']} memiliki realisasi anggaran "
                f"{row['spend_pct']}% dan status program {row['program_status']}."
            )
        if {"region", "category", "service", "spend_pct", "program_status"}.issubset(row):
            return (
                f"{row['region']} - {row['service']} ({row['category']}) memiliki realisasi "
                f"anggaran {row['spend_pct']}% dan status program {row['program_status']}."
            )
        if {"region", "service", "topic", "severity", "complaint_count"}.issubset(row):
            return (
                f"{row['region']} - {row['service']} paling menonjol pada topik "
                f"'{row['topic']}' dengan severity {row['severity']} dan "
                f"{row['complaint_count']} keluhan."
            )
        if {"region", "service", "sla_days", "avg_resolution_days", "days_over_sla"}.issubset(row):
            return (
                f"{row['region']} - {row['service']} rata-rata selesai dalam "
                f"{row['avg_resolution_days']} hari, melewati SLA {row['sla_days']} hari "
                f"sekitar {row['days_over_sla']} hari."
            )
        if {"service", "category", "total_requests", "total_completed", "total_backlog"}.issubset(row):
            return (
                f"{row['service']} ({row['category']}) memiliki {row['total_requests']} request, "
                f"{row['total_completed']} selesai, dan total backlog {row['total_backlog']}."
            )
        if {"region", "service", "avg_satisfaction", "avg_resolution_days"}.issubset(row):
            return (
                f"{row['region']} - {row['service']} memiliki rata-rata kepuasan "
                f"{row['avg_satisfaction']} dan rata-rata penyelesaian "
                f"{row['avg_resolution_days']} hari."
            )
        return ", ".join(f"{key}: {value}" for key, value in row.items())

    @staticmethod
    def _quality_check(
        answer: str,
        has_sql: bool,
        has_citations: bool,
        has_risk_signal: bool = False,
    ) -> str:
        answer_lower = answer.lower()
        if (
            "menolak menjalankan permintaan destructive sql" in answer_lower
            or "tidak bisa membantu menjalankan" in answer_lower
        ):
            return "grounded"
        if "data tidak tersedia" in answer_lower:
            return "grounded"
        if (has_sql or has_citations or has_risk_signal) and len(answer.strip()) > 40:
            return "grounded"
        return "needs_review"

    def _quality_trace(
        self,
        question: str,
        answer: str,
        has_sql: bool,
        has_citations: bool,
        quality: str | None = None,
        has_risk_signal: bool = False,
    ) -> ToolTrace:
        started = time.perf_counter()
        result = quality or self._quality_check(answer, has_sql, has_citations, has_risk_signal)
        return ToolTrace(
            agent="Quality Checker Agent",
            tool="validate_answer_grounding",
            input=question,
            output_preview=result,
            status="ok" if result == "grounded" else "needs_review",
            duration_ms=self._elapsed_ms(started),
        )

    @staticmethod
    def _confidence_for(
        route: str,
        quality: str,
        sql_result: SQLResult | None,
        citations: list[RetrievalHit],
    ) -> float:
        if route == "unsupported":
            return 0.42
        if route == "guardrail":
            return 0.95
        if quality != "grounded":
            return 0.66
        if sql_result and citations:
            return 0.89
        if sql_result or citations:
            return 0.86
        return 0.74

    @staticmethod
    def _citation_from_hit(hit: RetrievalHit) -> Citation:
        return Citation(source=hit.source, title=hit.title, snippet=hit.snippet, score=hit.score)

    @staticmethod
    def _sql_preview(result: SQLResult | None) -> SQLPreview | None:
        if not result:
            return None
        return SQLPreview(query=result.query, columns=result.columns, rows=result.rows[:10])

    @staticmethod
    def _polish_prompt(
        question: str,
        response: ChatResponse,
        conversation_history: list[ChatHistoryMessage],
    ) -> str:
        return json.dumps(
            {
                "user_question": question,
                "draft_answer": response.answer,
                "current_session_history": [
                    item.model_dump() for item in conversation_history[-12:]
                ],
                "data_rows": response.sql.rows if response.sql else [],
                "source_snippets": [
                    {"title": item.title, "snippet": item.snippet}
                    for item in response.citations
                ],
            },
            ensure_ascii=False,
        )

    @staticmethod
    def _chat_prompt(
        question: str,
        response: ChatResponse,
        conversation_history: list[ChatHistoryMessage],
    ) -> str:
        has_local_evidence = bool(response.sql or response.citations)
        has_curated_draft = has_local_evidence or response.route in {
            "catalog",
            "conversation",
            "guardrail",
        }
        local_context = {
            "user_question": question,
            "draft_answer": response.answer if has_curated_draft else "",
            "current_session_history": [
                item.model_dump() for item in conversation_history[-12:]
            ],
            "data_rows": response.sql.rows if response.sql else [],
            "source_snippets": [
                {"title": item.title, "snippet": item.snippet}
                for item in response.citations
            ],
            "has_local_evidence": has_local_evidence,
            "has_curated_draft": has_curated_draft,
        }
        return json.dumps(local_context, ensure_ascii=False)

    @staticmethod
    def _chat_confidence(response: ChatResponse) -> float:
        if response.sql and response.citations:
            return 0.92
        if response.sql or response.citations:
            return 0.89
        if response.route == "general":
            return 0.78
        return min(round(response.confidence + 0.04, 2), 0.94)

    @staticmethod
    def _compose_general_fallback_answer(question: str) -> str:
        return (
            "Saya bisa bantu menjawab seperti chatbot umum, tetapi mode AI chat sedang tidak tersedia. "
            "Untuk saat ini, saya paling siap membantu analisis data layanan publik di demo ini: backlog, SLA, "
            "keluhan, anggaran, kebijakan, dan risiko wilayah.\n\n"
            f"Pertanyaan kamu: {question}"
        )

    @staticmethod
    def _sanitize_chat_answer(answer: str) -> str:
        answer = (
            answer.replace("\u2014", "-")
            .replace("\u2013", "-")
            .replace("\u201c", '"')
            .replace("\u201d", '"')
            .replace("\u2018", "'")
            .replace("\u2019", "'")
        )
        blocked_exact = {"ringkasan", "temuan utama", "evidence", "rekomendasi"}
        blocked_prefixes = ("confidence:", "route:", "sql:", "select ")
        lines = []
        for line in answer.splitlines():
            stripped = line.strip()
            lowered = stripped.lower()
            if lowered in blocked_exact:
                continue
            if lowered.startswith(blocked_prefixes):
                continue
            if any(term in lowered for term in ANTI_PATTERN_TERMS):
                continue
            if "function_call" in lowered or "agent trace" in lowered:
                continue
            lines.append(line.rstrip())
        return "\n".join(lines).strip()

    @staticmethod
    def _normalize_conversation_history(
        conversation_history: list[ChatHistoryMessage | dict] | None,
    ) -> list[ChatHistoryMessage]:
        normalized: list[ChatHistoryMessage] = []
        for item in conversation_history or []:
            try:
                if isinstance(item, ChatHistoryMessage):
                    normalized.append(item)
                elif isinstance(item, dict):
                    normalized.append(ChatHistoryMessage.model_validate(item))
            except Exception:
                continue
        return normalized[-20:]

    @staticmethod
    def _is_context_reference_question(question: str) -> bool:
        q = question.lower()
        return any(
            phrase in q
            for phrase in [
                "anda bilang",
                "kamu bilang",
                "sebelumnya",
                "tadi",
                "barusan",
                "bukankah",
                "jawaban sebelumnya",
                "pesan sebelumnya",
                "riwayat",
            ]
        )

    def _compose_context_reference_answer(
        self,
        question: str,
        conversation_history: list[ChatHistoryMessage],
    ) -> str:
        q = question.lower()
        if not conversation_history:
            return (
                "Riwayat percakapan tidak dikirim bersama permintaan ini, "
                "jadi saya belum bisa memverifikasi klaim sebelumnya."
            )

        claim = self._find_relevant_assistant_claim(question, conversation_history)
        if "wilayah" in q:
            wilayah = "Palangka Raya, Kotawaringin Barat, Kapuas, Barito Utara, dan Murung Raya"
            if claim and any(term in claim.lower() for term in ["tidak ada", "tidak tersedia"]):
                return (
                    "Benar, jawaban saya sebelumnya keliru. "
                    f"Yang benar, dataset ini memang memiliki data wilayah: {wilayah}."
                )
            if claim:
                return (
                    "Ya, sebelumnya saya menyebut ada data wilayah. "
                    f"Rinciannya: {wilayah}."
                )
            return (
                "Saya melihat riwayat sesi ini, tetapi tidak menemukan klaim sebelumnya tentang data wilayah. "
                f"Yang benar, dataset demo ini memiliki data wilayah: {wilayah}."
            )

        if claim:
            return f"Ya, sebelumnya saya menyebut: {claim.rstrip('.')}."

        return (
            "Saya melihat riwayat sesi ini, tetapi tidak menemukan klaim sebelumnya yang cocok dengan pertanyaan itu."
        )

    @staticmethod
    def _find_relevant_assistant_claim(
        question: str,
        conversation_history: list[ChatHistoryMessage],
    ) -> str | None:
        q = question.lower()
        keywords = [
            term
            for term in ["wilayah", "data", "anggaran", "keluhan", "kpi", "sla", "layanan"]
            if term in q
        ]
        if not keywords:
            keywords = ["sebelumnya", "tadi", "bilang"]

        for message in reversed(conversation_history):
            if message.role != "assistant":
                continue
            lines = [line.strip(" -") for line in message.content.splitlines() if line.strip()]
            for line in lines:
                lowered = line.lower()
                if any(keyword in lowered for keyword in keywords):
                    return line[:500]
        return None

    @staticmethod
    def _normalize_answer_mode(answer_mode: str) -> AnswerMode:
        if answer_mode == "fast":
            return "fast"
        if answer_mode == "polish":
            return "polish"
        return "chat"

    @classmethod
    def _has_sql_intent(cls, question: str) -> bool:
        return any(term in question for term in cls.SQL_TERMS)

    @classmethod
    def _has_doc_intent(cls, question: str) -> bool:
        return any(term in question for term in cls.DOC_TERMS)

    @classmethod
    def _has_risk_intent(cls, question: str) -> bool:
        return any(term in question for term in cls.RISK_TERMS)

    @classmethod
    def _mentions_known_region(cls, question: str) -> bool:
        return any(term in question for term in cls.REGION_TERMS)

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

    @staticmethod
    def _is_catalog_question(question: str) -> bool:
        q = question.lower()
        if any(phrase in q for phrase in ["tidak tersedia", "tidak ada", "belum tersedia"]):
            return False
        return any(phrase in q for phrase in SatuDataOpsAgent.CATALOG_SUMMARY_PHRASES)

    @classmethod
    def _is_catalog_detail_question(
        cls,
        question: str,
        conversation_history: list[ChatHistoryMessage],
    ) -> bool:
        q = question.lower()
        if any(phrase in q for phrase in cls.CATALOG_DETAIL_PHRASES):
            return True
        if not cls._history_mentions_catalog(conversation_history):
            return False
        return "data" in q and any(term in q for term in cls.CATALOG_FOLLOWUP_TERMS)

    @classmethod
    def _history_mentions_catalog(cls, conversation_history: list[ChatHistoryMessage]) -> bool:
        for message in reversed(conversation_history):
            if message.role != "assistant":
                continue
            lowered = message.content.lower()
            label_hits = sum(label in lowered for label in cls.CATALOG_CATEGORY_LABELS)
            if label_hits >= 2:
                return True
        return False

    def _policy_document_titles(self) -> list[str]:
        titles: list[str] = []
        for path in sorted(Path(self.rag.docs_path).glob("*.md")):
            text = path.read_text(encoding="utf-8")
            title = self._policy_title_from_text(text, fallback=path.stem.replace("_", " ").title())
            titles.append(title)
        return titles

    @staticmethod
    def _policy_title_from_text(text: str, fallback: str) -> str:
        for line in text.splitlines():
            if line.startswith("# "):
                return line.removeprefix("# ").strip()
        return fallback

    @staticmethod
    def _elapsed_ms(started: float) -> float:
        return round((time.perf_counter() - started) * 1000, 1)
