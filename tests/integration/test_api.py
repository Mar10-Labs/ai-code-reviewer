import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, AsyncMock, MagicMock

from src.api.main import app


@pytest.fixture
def client():
    return TestClient(app)


class TestHealthEndpoint:
    def test_health_check_returns_ok(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

    def test_health_check_content_type(self, client):
        response = client.get("/health")
        assert response.headers["content-type"] == "application/json"


class TestAgentEndpoints:
    def test_get_commands_returns_list(self, client):
        response = client.get("/agent/commands")
        assert response.status_code == 200
        data = response.json()
        assert "commands" in data
        assert isinstance(data["commands"], list)
        assert len(data["commands"]) > 0

    def test_get_commands_contains_review(self, client):
        response = client.get("/agent/commands")
        commands = response.json()["commands"]
        command_text = " ".join(commands)
        assert "review" in command_text.lower()

    def test_get_history_returns_list(self, client):
        response = client.get("/agent/history")
        assert response.status_code == 200
        data = response.json()
        assert "history" in data
        assert isinstance(data["history"], list)

    def test_get_status_returns_message(self, client):
        response = client.get("/agent/status")
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert "graph" in data or "nodes" in data

    def test_post_command_review(self, client):
        response = client.post(
            "/agent/command",
            json={"command": "review pr"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "intent" in data
        assert "message" in data

    def test_post_command_help(self, client):
        response = client.post(
            "/agent/command",
            json={"command": "help", "auto_mode": False}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["intent"] == "help"

    def test_post_command_unknown_shows_error(self, client):
        response = client.post(
            "/agent/command",
            json={"command": "invalid command xyz", "auto_mode": False}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["intent"] == "unknown"


class TestReviewEndpoint:
    def test_review_endpoint(self, client):
        response = client.post(
            "/agent/review",
            params={
                "diff_content": "def test(): pass",
                "repository": "test/repo",
                "pr_number": 1
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert "intent" in data
        assert "agent_results" in data
        assert "summary" in data


class TestOpenAPISchema:
    def test_openapi_schema_available(self, client):
        response = client.get("/openapi.json")
        assert response.status_code == 200
        data = response.json()
        assert "openapi" in data
        assert "paths" in data

    def test_docs_available(self, client):
        response = client.get("/docs")
        assert response.status_code == 200

    def test_redoc_available(self, client):
        response = client.get("/redoc")
        assert response.status_code == 200


class TestAPIEndpoints:
    def test_root_returns_404(self, client):
        response = client.get("/")
        assert response.status_code == 404

    def test_nonexistent_endpoint_returns_404(self, client):
        response = client.get("/nonexistent")
        assert response.status_code == 404


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
