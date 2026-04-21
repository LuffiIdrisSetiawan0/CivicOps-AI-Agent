from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import app


def test_health_endpoint(monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    get_settings.cache_clear()

    with TestClient(app) as client:
        response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_chat_endpoint(monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
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
    assert body["trace"]
    assert body["sql"] is not None


def test_eval_endpoint(monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    get_settings.cache_clear()

    with TestClient(app) as client:
        response = client.post("/api/eval/run")

    body = response.json()
    assert response.status_code == 200
    assert body["total"] == 20
    assert body["passed"] >= 16

