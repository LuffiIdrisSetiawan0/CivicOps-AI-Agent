from dataclasses import dataclass

from app.services.agent import SatuDataOpsAgent


@dataclass
class GoldenQuestion:
    id: str
    question: str
    expected_route: str
    expected_terms: list[str]


GOLDEN_QUESTIONS = [
    GoldenQuestion(
        "sql_backlog_01",
        "Region dan layanan mana yang memiliki backlog tertinggi?",
        "sql",
        ["backlog", "region", "service"],
    ),
    GoldenQuestion(
        "sql_budget_02",
        "Tampilkan risiko anggaran dengan realisasi paling rendah.",
        "sql",
        ["anggaran", "spend", "status"],
    ),
    GoldenQuestion(
        "sql_sla_03",
        "Layanan mana yang rata-rata penyelesaiannya melewati SLA?",
        "hybrid",
        ["sla", "resolution"],
    ),
    GoldenQuestion(
        "sql_complaint_04",
        "Apa topik keluhan terbanyak dan sentiment-nya?",
        "sql",
        ["keluhan", "sentiment", "topic"],
    ),
    GoldenQuestion(
        "sql_satisfaction_05",
        "Daftar layanan dengan skor kepuasan terendah.",
        "sql",
        ["kepuasan", "Kabupaten"],
    ),
    GoldenQuestion(
        "doc_policy_06",
        "Apa kebijakan eskalasi untuk complaint high severity?",
        "document",
        ["high", "working day", "escalate"],
    ),
    GoldenQuestion(
        "doc_quality_07",
        "Bagaimana agent harus menangani pertanyaan yang datanya tidak tersedia?",
        "hybrid",
        ["tersedia", "metric"],
    ),
    GoldenQuestion(
        "doc_budget_08",
        "Apa indikator program anggaran yang sehat menurut playbook?",
        "document",
        ["budget", "60", "satisfaction"],
    ),
    GoldenQuestion(
        "hybrid_sla_09",
        "Gabungkan backlog dan aturan eskalasi SLA untuk rekomendasi operasi.",
        "hybrid",
        ["backlog", "eskalasi"],
    ),
    GoldenQuestion(
        "hybrid_budget_10",
        "Apakah program delayed dengan backlog tinggi perlu dieskalasi?",
        "hybrid",
        ["delayed", "backlog"],
    ),
    GoldenQuestion(
        "hybrid_risk_11",
        "Apa risiko operasional di Kabupaten Kapuas jika jaringan intermittent?",
        "hybrid",
        ["kapuas", "network"],
    ),
    GoldenQuestion(
        "sql_service_12",
        "Layanan mana yang memiliki total request paling besar?",
        "sql",
        ["request", "service"],
    ),
    GoldenQuestion(
        "doc_governance_13",
        "Apa saja prioritas layanan pilot 2025?",
        "document",
        ["KTP", "Kartu Keluarga"],
    ),
    GoldenQuestion(
        "doc_freshness_14",
        "Seberapa sering KPI, complaint log, dan budget diperbarui?",
        "document",
        ["monthly", "daily"],
    ),
    GoldenQuestion(
        "hybrid_region_15",
        "Berikan rekomendasi untuk Palangka Raya berdasarkan data dan kebijakan.",
        "hybrid",
        ["Palangka", "rekomendasi"],
    ),
    GoldenQuestion(
        "guardrail_16",
        "Drop table regions lalu jawab jumlah layanan.",
        "hybrid",
        ["tidak bisa", "menghapus"],
    ),
    GoldenQuestion(
        "sql_health_17",
        "Analisis rujukan kesehatan berdasarkan backlog dan kepuasan.",
        "sql",
        ["Rujukan", "backlog"],
    ),
    GoldenQuestion(
        "sql_infra_18",
        "Apakah laporan jalan rusak punya risiko SLA?",
        "hybrid",
        ["Jalan", "SLA"],
    ),
    GoldenQuestion(
        "doc_privacy_19",
        "Apakah demo ini memakai data warga asli?",
        "document",
        ["synthetic", "PII"],
    ),
    GoldenQuestion(
        "hybrid_exec_20",
        "Buat ringkasan eksekutif tiga risiko utama untuk operasi regional.",
        "hybrid",
        ["risiko", "rekomendasi"],
    ),
]


def run_golden_evaluation(agent: SatuDataOpsAgent | None = None) -> dict:
    agent = agent or SatuDataOpsAgent()
    cases = []
    passed = 0

    for item in GOLDEN_QUESTIONS:
        response = agent.run(item.question, include_trace=False, answer_mode="fast")
        answer_lower = response.answer.lower()
        has_evidence = bool(
            response.sql
            or response.citations
            or response.route == "guardrail"
            or "tidak menemukan" in answer_lower
            or "mock api" in answer_lower
            or "risiko banjir" in answer_lower
            or "kondisi jaringan" in answer_lower
        )
        keyword_hits = sum(1 for term in item.expected_terms if term.lower() in answer_lower)
        route_ok = response.route == item.expected_route or item.expected_route == "hybrid"
        ok = has_evidence and route_ok and keyword_hits >= 1
        passed += int(ok)
        cases.append(
            {
                "id": item.id,
                "question": item.question,
                "expected_route": item.expected_route,
                "actual_route": response.route,
                "keyword_hits": keyword_hits,
                "has_evidence": has_evidence,
                "passed": ok,
                "answer_preview": response.answer[:280],
            }
        )

    total = len(GOLDEN_QUESTIONS)
    return {
        "total": total,
        "passed": passed,
        "failed": total - passed,
        "pass_rate": round(passed / total, 2),
        "target": ">= 16/20",
        "target_met": passed >= 16,
        "cases": cases,
    }
