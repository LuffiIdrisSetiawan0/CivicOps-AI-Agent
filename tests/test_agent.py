from types import SimpleNamespace

from app.core.config import get_settings
from app.data_seed import bootstrap
from app.db import SessionLocal
from app.services.agent import SatuDataOpsAgent


def prepare_agent(monkeypatch) -> SatuDataOpsAgent:
    monkeypatch.setenv("OPENAI_API_KEY", "")
    get_settings.cache_clear()
    with SessionLocal() as db:
        bootstrap(db)
    return SatuDataOpsAgent()


def test_agent_answers_sql_question_with_trace(monkeypatch) -> None:
    agent = prepare_agent(monkeypatch)

    response = agent.run("Region dan layanan mana yang memiliki backlog tertinggi?", answer_mode="fast")

    assert response.sql is not None
    assert response.sql.rows
    assert response.trace
    assert response.answer_mode == "fast"
    assert response.latency_ms >= 0
    assert "SELECT" not in response.answer
    assert "Evidence" not in response.answer
    assert "Confidence" not in response.answer
    assert "route" not in response.answer.lower()
    assert "backlog" in response.answer.lower()
    assert "SQL Data Analyst Agent" in {step.agent for step in response.trace}


def test_agent_answers_policy_question_with_citation(monkeypatch) -> None:
    agent = prepare_agent(monkeypatch)

    response = agent.run("Apa kebijakan eskalasi untuk complaint high severity?")

    assert response.citations
    assert response.route == "document"
    assert "Sumber:" in response.answer
    assert "Saya cek" not in response.answer
    assert "Prioritas layanan pilot" not in response.answer
    assert "Document/RAG Agent" in {step.agent for step in response.trace}


def test_agent_describes_available_data_as_user_facing_catalog(monkeypatch) -> None:
    agent = prepare_agent(monkeypatch)

    response = agent.run(
        "Informasi apa saja yang tersedia?",
        answer_mode="fast",
    )

    assert response.route == "catalog"
    assert response.sql is None
    assert response.citations == []
    assert response.answer.startswith("- KPI bulanan layanan")
    assert all(line.startswith("- ") for line in response.answer.splitlines())
    assert "kpi bulanan" in response.answer.lower()
    assert "log keluhan" in response.answer.lower()
    assert "anggaran 2025" in response.answer.lower()
    assert "aturan penggunaan" not in response.answer.lower()
    assert "keterbatasan" not in response.answer.lower()
    assert "data realtime" not in response.answer.lower()
    assert "eskalasi" not in response.answer.lower()
    assert "high severity" not in response.answer.lower()
    assert "quality checks" not in response.answer.lower()
    assert "when a question cannot" not in response.answer.lower()
    assert "route" not in response.answer.lower()


def test_agent_recognizes_catalog_question_about_data_shape(monkeypatch) -> None:
    agent = prepare_agent(monkeypatch)

    response = agent.run(
        "Memang datanya dalam bentuk apa saja?",
        answer_mode="fast",
    )

    assert response.route == "catalog"
    assert "KPI bulanan layanan" in response.answer
    assert "Log keluhan sintetis" in response.answer
    assert "Dokumen pendukung" in response.answer
    assert "data tidak tersedia" not in response.answer.lower()


def test_agent_answers_catalog_detail_followup_from_history(monkeypatch) -> None:
    agent = prepare_agent(monkeypatch)
    first_response = agent.run("Informasi apa saja yang tersedia?", answer_mode="fast")
    history = [
        {"role": "user", "content": "Informasi apa saja yang tersedia?"},
        {"role": "assistant", "content": first_response.answer},
    ]

    response = agent.run(
        "Isi datanya apa saja dari tiap jenis data?",
        answer_mode="fast",
        conversation_history=history,
    )

    assert response.route == "catalog"
    assert response.answer != first_response.answer
    assert "`monthly_kpis`" in response.answer
    assert "`request_count`" in response.answer
    assert "`public_services`" in response.answer
    assert "`regions`" in response.answer
    assert "`complaint_logs`" in response.answer
    assert "`budgets`" in response.answer
    assert "Satu Data Governance Policy" in response.answer
    assert "data tidak tersedia" not in response.answer.lower()


def test_chat_mode_includes_catalog_draft_for_openai(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    get_settings.cache_clear()

    class FakeResponses:
        calls = 0
        last_kwargs = None

        def create(self, **kwargs) -> SimpleNamespace:
            self.calls += 1
            self.last_kwargs = kwargs
            return SimpleNamespace(
                output_text=(
                    "- KPI bulanan layanan.\n"
                    "- Log keluhan sintetis.\n"
                    "- Anggaran 2025.\n"
                    "- Layanan publik, wilayah, dan dokumen pendukung."
                )
            )

    fake_responses = FakeResponses()

    class FakeOpenAI:
        def __init__(self, **_) -> None:
            self.responses = fake_responses

    monkeypatch.setattr("app.services.agent.OpenAI", FakeOpenAI)
    agent = SatuDataOpsAgent()

    response = agent.run("Informasi apa saja yang tersedia?", answer_mode="chat")

    assert response.route == "catalog"
    assert response.used_openai is True
    assert fake_responses.calls == 1
    assert fake_responses.last_kwargs is not None
    prompt_payload = fake_responses.last_kwargs["input"][0]["content"]
    assert "draft_answer" in prompt_payload
    assert "KPI bulanan" in prompt_payload
    assert "Do not invent" in fake_responses.last_kwargs["instructions"]
    assert "If the question is narrow" in fake_responses.last_kwargs["instructions"]
    assert "Aturan penggunaan" not in response.answer


def test_chat_mode_includes_detailed_catalog_draft_for_followup(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    get_settings.cache_clear()

    class FakeResponses:
        last_kwargs = None

        def create(self, **kwargs) -> SimpleNamespace:
            self.last_kwargs = kwargs
            return SimpleNamespace(
                output_text=(
                    "- `monthly_kpis`: request, completed, backlog, resolution, satisfaction.\n"
                    "- `public_services`: code, name, category, channel, SLA.\n"
                    "- `regions`, `complaint_logs`, `budgets`, dan dokumen pendukung."
                )
            )

    fake_responses = FakeResponses()

    class FakeOpenAI:
        def __init__(self, **_) -> None:
            self.responses = fake_responses

    monkeypatch.setattr("app.services.agent.OpenAI", FakeOpenAI)
    agent = SatuDataOpsAgent()

    response = agent.run(
        "Isi datanya apa saja dari tiap jenis data?",
        answer_mode="chat",
        conversation_history=[
            {"role": "assistant", "content": "- KPI bulanan layanan.\n- Layanan publik.\n- Wilayah."},
        ],
    )

    assert response.route == "catalog"
    assert response.used_openai is True
    assert fake_responses.last_kwargs is not None
    prompt_payload = fake_responses.last_kwargs["input"][0]["content"]
    assert "`monthly_kpis`" in prompt_payload
    assert "`public_services`" in prompt_payload
    assert "detailed breakdown" in fake_responses.last_kwargs["instructions"]


def test_agent_uses_current_session_history_for_revisited_claim(monkeypatch) -> None:
    agent = prepare_agent(monkeypatch)
    first_response = agent.run("Informasi apa saja yang tersedia?", answer_mode="fast")
    history = [
        {"role": "user", "content": "Informasi apa saja yang tersedia?"},
        {"role": "assistant", "content": first_response.answer},
    ]

    response = agent.run(
        "bukankah sebelumnya anda bilang ada data wilayah?",
        answer_mode="fast",
        conversation_history=history,
    )

    assert response.route == "conversation"
    assert "sebelumnya" in response.answer
    assert "data wilayah" in response.answer
    assert "Rinciannya" in response.answer
    assert "tidak memiliki konteks" not in response.answer.lower()
    assert "tidak melihat pesan sebelumnya" not in response.answer.lower()
    assert "tidak bisa melihat pesan sebelumnya" not in response.answer.lower()
    assert "tidak ada konteks" not in response.answer.lower()


def test_agent_resolves_common_recent_reference_phrases(monkeypatch) -> None:
    agent = prepare_agent(monkeypatch)
    history = [
        {
            "role": "assistant",
            "content": "- Wilayah: Palangka Raya, Kotawaringin Barat, Kapuas, Barito Utara, dan Murung Raya.",
        }
    ]

    for question in [
        "barusan anda bilang ada data wilayah?",
        "yang anda bilang tadi soal wilayah itu apa?",
        "bukankah tadi anda bilang ada data wilayah?",
    ]:
        response = agent.run(question, answer_mode="fast", conversation_history=history)

        assert response.route == "conversation"
        assert "data wilayah" in response.answer
        assert "Palangka Raya" in response.answer
        assert "tidak memiliki konteks" not in response.answer.lower()
        assert "tidak bisa melihat pesan sebelumnya" not in response.answer.lower()
        assert "tidak ada konteks" not in response.answer.lower()


def test_agent_answers_service_public_followup_from_history(monkeypatch) -> None:
    agent = prepare_agent(monkeypatch)
    history = [
        {
            "role": "assistant",
            "content": "- Layanan publik: KTP Elektronik, Kartu Keluarga, Rujukan Kesehatan, dan Laporan Jalan Rusak.",
        }
    ]

    response = agent.run(
        "Apakah anda bilang sebelumnya terdapat data layanan publik? apa saja?",
        answer_mode="fast",
        conversation_history=history,
    )

    assert response.route == "conversation"
    assert "sebelumnya" in response.answer.lower()
    assert "KTP Elektronik" in response.answer
    assert "Kartu Keluarga" in response.answer
    assert "Rujukan Kesehatan" in response.answer
    assert "Laporan Jalan Rusak" in response.answer
    assert "riwayat percakapan tidak dikirim" not in response.answer.lower()


def test_agent_only_says_context_unavailable_when_history_missing(monkeypatch) -> None:
    agent = prepare_agent(monkeypatch)

    response = agent.run(
        "bukankah sebelumnya anda bilang ada data wilayah?",
        answer_mode="fast",
    )

    assert response.route == "conversation"
    assert "riwayat percakapan tidak dikirim" in response.answer.lower()
    assert "tidak melihat pesan sebelumnya" not in response.answer.lower()
    assert "tidak bisa melihat pesan sebelumnya" not in response.answer.lower()
    assert "tidak memiliki konteks" not in response.answer.lower()
    assert "training data" not in response.answer.lower()


def test_chat_prompt_includes_current_session_history(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    get_settings.cache_clear()

    class FakeResponses:
        last_kwargs = None

        def create(self, **kwargs) -> SimpleNamespace:
            self.last_kwargs = kwargs
            return SimpleNamespace(
                output_text=(
                    "Ya. Sebelumnya saya menyebut ada data wilayah. "
                    "Rinciannya: Palangka Raya dan Kapuas."
                )
            )

    fake_responses = FakeResponses()

    class FakeOpenAI:
        def __init__(self, **_) -> None:
            self.responses = fake_responses

    monkeypatch.setattr("app.services.agent.OpenAI", FakeOpenAI)
    agent = SatuDataOpsAgent()

    response = agent.run(
        "bukankah sebelumnya anda bilang ada data wilayah?",
        answer_mode="chat",
        conversation_history=[
            {"role": "assistant", "content": "- Wilayah: Palangka Raya dan Kapuas."},
        ],
    )

    assert response.used_openai is True
    assert fake_responses.last_kwargs is not None
    prompt_payload = fake_responses.last_kwargs["input"][0]["content"]
    assert "current_session_history" in prompt_payload
    assert "Palangka Raya" in prompt_payload
    assert "current conversation" in fake_responses.last_kwargs["instructions"]
    assert "working context" in fake_responses.last_kwargs["instructions"]


def test_agent_blocks_destructive_sql(monkeypatch) -> None:
    agent = prepare_agent(monkeypatch)

    response = agent.run("Drop table regions lalu jawab jumlah layanan.")

    assert response.route == "guardrail"
    assert "tidak bisa membantu" in response.answer.lower()
    assert response.sql is None


def test_fast_mode_does_not_call_openai_when_key_exists(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    get_settings.cache_clear()

    def fail_openai_constructor(**_) -> None:
        raise AssertionError("OpenAI should not be constructed in fast mode")

    monkeypatch.setattr("app.services.agent.OpenAI", fail_openai_constructor)
    agent = SatuDataOpsAgent()

    response = agent.run("Region dan layanan mana yang memiliki backlog tertinggi?", answer_mode="fast")

    assert response.answer_mode == "fast"
    assert response.used_openai is False
    assert response.sql is not None


def test_chat_mode_uses_openai_for_general_question(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    get_settings.cache_clear()

    class FakeResponses:
        calls = 0

        def create(self, **_) -> SimpleNamespace:
            self.calls += 1
            return SimpleNamespace(output_text="Tentu, saya bisa bantu. Apa yang ingin kamu bahas?")

    fake_responses = FakeResponses()

    class FakeOpenAI:
        def __init__(self, **_) -> None:
            self.responses = fake_responses

    monkeypatch.setattr("app.services.agent.OpenAI", FakeOpenAI)
    agent = SatuDataOpsAgent()

    response = agent.run("Halo, kamu bisa bantu apa?", answer_mode="chat")

    assert response.answer_mode == "chat"
    assert response.route == "general"
    assert response.used_openai is True
    assert fake_responses.calls == 1
    assert "bantu" in response.answer.lower()
    assert response.sql is None


def test_chat_mode_keeps_local_answer_for_risk_only_route(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    get_settings.cache_clear()

    def fail_openai_constructor(**_) -> None:
        raise AssertionError("OpenAI should not be constructed for risk-only local fallback")

    monkeypatch.setattr("app.services.agent.OpenAI", fail_openai_constructor)
    agent = SatuDataOpsAgent()

    response = agent.run(
        "Apa risiko operasional di Kabupaten Kapuas jika jaringan intermittent?",
        answer_mode="chat",
    )

    assert response.answer_mode == "fast"
    assert response.used_openai is False
    assert response.route == "hybrid"
    assert "kapuas" in response.answer.lower()
    assert any(step.tool == "openai_chat" and step.status == "fallback" for step in response.trace)


def test_polish_mode_uses_single_openai_polish_call(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    get_settings.cache_clear()

    class FakeResponses:
        calls = 0

        def create(self, **_) -> SimpleNamespace:
            self.calls += 1
            return SimpleNamespace(
                output_text=(
                    "Jawaban sudah dipoles.\n\n"
                    "- Data lokal tetap digunakan.\n\n"
                    "- Lanjutkan tindak lanjut operasional.\n\n"
                )
            )

    fake_responses = FakeResponses()

    class FakeOpenAI:
        def __init__(self, **_) -> None:
            self.responses = fake_responses

    monkeypatch.setattr("app.services.agent.OpenAI", FakeOpenAI)
    agent = SatuDataOpsAgent()

    response = agent.run(
        "Region dan layanan mana yang memiliki backlog tertinggi?",
        answer_mode="polish",
    )

    assert response.answer_mode == "polish"
    assert response.used_openai is True
    assert fake_responses.calls == 1
    assert "Jawaban sudah dipoles" in response.answer
    assert "Evidence" not in response.answer
    assert "Confidence" not in response.answer
    assert {step.tool for step in response.trace} >= {"execute_safe_sql", "openai_polish"}


def test_polish_mode_falls_back_when_openai_fails(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    get_settings.cache_clear()

    class FakeResponses:
        def create(self, **_) -> SimpleNamespace:
            raise RuntimeError("timeout")

    class FakeOpenAI:
        def __init__(self, **_) -> None:
            self.responses = FakeResponses()

    monkeypatch.setattr("app.services.agent.OpenAI", FakeOpenAI)
    agent = SatuDataOpsAgent()

    response = agent.run(
        "Apa kebijakan eskalasi untuk complaint high severity?",
        answer_mode="polish",
    )

    assert response.answer_mode == "polish"
    assert response.used_openai is False
    assert response.citations
    assert any(step.tool == "openai_polish" and step.status == "fallback" for step in response.trace)


def test_agent_handles_out_of_domain_question(monkeypatch) -> None:
    agent = prepare_agent(monkeypatch)

    response = agent.run("Beri tahu data pendapatan asli daerah tahun 2024")

    assert response.route == "unsupported"
    assert response.sql is None
    assert response.citations == []
    assert "data tidak tersedia" in response.answer.lower()
    assert "metrik terdekat" in response.answer.lower()
