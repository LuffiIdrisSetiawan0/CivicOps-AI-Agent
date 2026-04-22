from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import app


def test_health_endpoint(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "")
    get_settings.cache_clear()

    with TestClient(app) as client:
        response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["default_answer_mode"] == "fast"


def test_index_uses_versioned_static_assets(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "")
    get_settings.cache_clear()

    with TestClient(app) as client:
        response = client.get("/")

    body = response.text
    assert response.status_code == 200
    assert "/static/styles.css?v=" in body
    assert "/static/app.js?v=" in body


def test_chat_endpoint(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "")
    get_settings.cache_clear()

    with TestClient(app) as client:
        response = client.post(
            "/api/chat",
            json={
                "question": "Gabungkan backlog dan aturan eskalasi SLA untuk rekomendasi operasi.",
                "include_trace": True,
            },
        )

    body = response.json()
    assert response.status_code == 200
    assert body["answer"]
    assert body["answer_mode"] == "fast"
    assert body["latency_ms"] >= 0
    assert body["trace"]
    assert body["sql"] is not None
    assert all("duration_ms" in step for step in body["trace"])


def test_chat_endpoint_accepts_conversation_history(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "")
    get_settings.cache_clear()

    with TestClient(app) as client:
        response = client.post(
            "/api/chat",
            json={
                "question": "bukankah sebelumnya anda bilang ada data wilayah?",
                "include_trace": False,
                "answer_mode": "fast",
                "conversation_history": [
                    {
                        "role": "assistant",
                        "content": "- Wilayah: Palangka Raya, Kapuas, dan Barito Utara.",
                    }
                ],
            },
        )

    body = response.json()
    assert response.status_code == 200
    assert body["route"] == "conversation"
    assert "data wilayah" in body["answer"]
    assert "tidak melihat pesan sebelumnya" not in body["answer"].lower()


def test_dashboard_summary_endpoint(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "")
    get_settings.cache_clear()

    with TestClient(app) as client:
        response = client.get("/api/dashboard/summary")

    body = response.json()
    assert response.status_code == 200
    assert body["snapshot_month"] == "2025-06"
    assert body["stats"]
    assert body["trend"]
    assert body["hotspots"]
    assert body["budget_watchlist"]
    assert body["suggested_questions"]


def test_chat_endpoint_defaults_to_polish_when_openai_is_configured(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    get_settings.cache_clear()

    class FakeResponses:
        def create(self, **_) -> SimpleNamespace:
            return SimpleNamespace(output_text="Jawaban polished.")

    class FakeOpenAI:
        def __init__(self, **_) -> None:
            self.responses = FakeResponses()

    monkeypatch.setattr("app.services.agent.OpenAI", FakeOpenAI)

    with TestClient(app) as client:
        response = client.post(
            "/api/chat",
            json={
                "question": "Gabungkan backlog dan aturan eskalasi SLA untuk rekomendasi operasi.",
                "include_trace": False,
            },
        )

    body = response.json()
    assert response.status_code == 200
    assert body["answer_mode"] == "polish"
    assert body["used_openai"] is True


def test_eval_endpoint(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "")
    get_settings.cache_clear()

    with TestClient(app) as client:
        response = client.post("/api/eval/run")

    body = response.json()
    assert response.status_code == 200
    assert body["total"] == 20
    assert body["passed"] >= 16
