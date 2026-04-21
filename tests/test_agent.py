from app.core.config import get_settings
from app.data_seed import bootstrap
from app.db import SessionLocal
from app.services.agent import SatuDataOpsAgent


def prepare_agent(monkeypatch) -> SatuDataOpsAgent:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    get_settings.cache_clear()
    with SessionLocal() as db:
        bootstrap(db)
    return SatuDataOpsAgent()


def test_agent_answers_sql_question_with_trace(monkeypatch) -> None:
    agent = prepare_agent(monkeypatch)

    response = agent.run("Region dan layanan mana yang memiliki backlog tertinggi?")

    assert response.sql is not None
    assert response.sql.rows
    assert response.trace
    assert "SQL Data Analyst Agent" in {step.agent for step in response.trace}


def test_agent_answers_policy_question_with_citation(monkeypatch) -> None:
    agent = prepare_agent(monkeypatch)

    response = agent.run("Apa kebijakan eskalasi untuk complaint high severity?")

    assert response.citations
    assert "Document/RAG Agent" in {step.agent for step in response.trace}


def test_agent_blocks_destructive_sql(monkeypatch) -> None:
    agent = prepare_agent(monkeypatch)

    response = agent.run("Drop table regions lalu jawab jumlah layanan.")

    assert response.route == "guardrail"
    assert "menolak" in response.answer.lower()
    assert response.sql is None

