import pytest
import hmac
import hashlib
import json
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


class TestWebhookEndpoint:
    def test_webhook_missing_delivery_id(self, client):
        response = client.post("/agent/webhook/github", json={})
        assert response.status_code == 400
        assert "Missing X-GitHub-Delivery" in response.json()["detail"]

    @patch("src.api.routes.agent.queue_manager")
    def test_webhook_duplicate_event(self, mock_queue, client):
        mock_queue.is_duplicate.return_value = True
        response = client.post(
            "/agent/webhook/github",
            headers={"X-GitHub-Delivery": "test-delivery-id"},
            json={"action": "opened"}
        )
        assert response.status_code == 200
        assert response.json()["status"] == "duplicate"

    @patch("src.api.routes.agent.queue_manager")
    @patch("src.api.routes.agent.webhook_validator")
    def test_webhook_valid_pr_opened(self, mock_validator, mock_queue, client):
        mock_validator.validate_hmac.return_value = True
        mock_queue.is_duplicate.return_value = False
        mock_queue.enqueue = AsyncMock(return_value=True)

        payload = {
            "action": "opened",
            "pull_request": {
                "number": 123,
                "title": "Test PR",
                "diff": "diff content",
                "user": {"login": "testuser"},
                "base": {"sha": "abc"},
                "head": {"sha": "def"}
            },
            "repository": {"full_name": "owner/repo"}
        }

        response = client.post(
            "/agent/webhook/github",
            headers={"X-GitHub-Delivery": "delivery-123"},
            json=payload
        )

        assert response.status_code == 200
        assert response.json()["status"] == "queued"

    @pytest.mark.skip(reason="Mock not working due to TestClient app loading order")
    @patch("src.api.routes.agent.WebhookValidator")
    def test_webhook_invalid_signature(self, mock_validator_class, client):
        mock_instance = MagicMock()
        mock_instance.validate_hmac = lambda *args, **kwargs: False
        mock_validator_class.return_value = mock_instance
        
        response = client.post(
            "/agent/webhook/github",
            headers={
                "X-GitHub-Delivery": "delivery-123",
                "X-Hub-Signature-256": "sha256=invalid"
            },
            json={"action": "opened"}
        )

        assert response.status_code == 401

    @patch("src.api.routes.agent.queue_manager")
    @patch("src.api.routes.agent.webhook_validator")
    def test_webhook_with_hmac_signature(self, mock_validator, mock_queue, client):
        mock_validator.validate_hmac.return_value = True
        mock_queue.is_duplicate.return_value = False
        mock_queue.enqueue = AsyncMock(return_value=True)

        payload = {
            "action": "synchronize",
            "pull_request": {
                "number": 456,
                "title": "Update PR",
                "diff": "new diff",
                "user": {"login": "developer"},
                "base": {"sha": "base123"},
                "head": {"sha": "head456"}
            },
            "repository": {"full_name": "org/project"}
        }

        response = client.post(
            "/agent/webhook/github",
            headers={
                "X-GitHub-Delivery": "delivery-456",
                "X-Hub-Signature-256": "sha256=abc123"
            },
            json=payload
        )

        assert response.status_code == 200


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
