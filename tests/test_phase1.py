from pathlib import Path

from fastapi.testclient import TestClient

from backend.config import get_settings
from backend.db.database import initialize_database
from backend.logging_config import redact
from main import app


def test_health_is_public() -> None:
    with TestClient(app) as client:
        response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_api_requires_session_token() -> None:
    settings = get_settings()
    with TestClient(app) as client:
        response = client.get("/api/example", headers={"Origin": settings.allowed_origins[0]})
    assert response.status_code == 401


def test_api_rejects_bad_origin() -> None:
    settings = get_settings()
    with TestClient(app) as client:
        response = client.get(
            "/api/example",
            headers={"Origin": "http://evil.example", "Authorization": f"Bearer {settings.app_session_token}"},
        )
    assert response.status_code == 403


def test_api_accepts_origin_and_token() -> None:
    settings = get_settings()
    with TestClient(app) as client:
        response = client.get(
            "/api/example",
            headers={"Origin": settings.allowed_origins[0], "Authorization": f"Bearer {settings.app_session_token}"},
        )
    assert response.status_code == 404


def test_api_allows_cors_preflight_without_bearer_token() -> None:
    settings = get_settings()
    with TestClient(app) as client:
        response = client.options(
            "/api/tasks",
            headers={
                "Origin": settings.allowed_origins[0],
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "authorization",
            },
        )
    assert response.status_code == 200


def test_database_migration_is_idempotent(tmp_path: Path) -> None:
    database_path = tmp_path / "agent.db"
    initialize_database(database_path)
    initialize_database(database_path)
    import sqlite3

    with sqlite3.connect(database_path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM schema_migrations").fetchone() == (6,)
        assert connection.execute("SELECT key FROM app_metadata").fetchall() == []


def test_redaction_hides_secret_values() -> None:
    assert "super-secret" not in redact("api_key=super-secret")
    assert "[REDACTED]" in redact("api_key=super-secret")
