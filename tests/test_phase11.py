from pathlib import Path

from fastapi.testclient import TestClient

from backend.config import get_settings
from main import create_app


def test_settings_require_session_token_and_never_expose_api_key(tmp_path: Path) -> None:
    app = create_app(database_path=tmp_path / "agent.db")
    settings = get_settings()
    origin = settings.allowed_origins[0]
    with TestClient(app) as client:
        assert client.get("/api/settings", headers={"Origin": origin}).status_code == 401
        headers = {"Origin": origin, "Authorization": f"Bearer {settings.app_session_token}"}
        response = client.get("/api/settings", headers=headers)
        assert response.status_code == 200
        assert "gemini_api_key" not in response.json()
        updated = client.put("/api/settings", headers=headers, json={"memory_enabled": False, "agent_max_steps": 7})
        assert updated.status_code == 200
        assert updated.json()["memory_enabled"] is False
        secret = client.put("/api/settings", headers=headers, json={"gemini_api_key": "secret"})
        assert secret.status_code == 422


def test_settings_are_not_registered_as_tools(tmp_path: Path) -> None:
    app = create_app(database_path=tmp_path / "agent.db")
    with TestClient(app):
        tools = app.state.agent_loop.registry.definitions()
        assert all("settings" not in tool.name.lower() for tool in tools)
        assert all("api_key" not in str(tool.parameters.model_json_schema()).lower() for tool in tools)
