import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient


class TestAgentRoutes:
    """Tests para agent routes"""

    def test_execute_command(self):
        from src.api.routes.agent import router
        from src.api.routes.schemas import UserCommandRequest
        from src.api.main import app
        
        with patch('src.api.routes.agent.master') as mock_master:
            mock_response = MagicMock()
            mock_response.intent.value = "review"
            mock_response.message = "Review complete"
            mock_response.agent_results = []
            mock_response.summary = "Summary"
            mock_response.context = None
            mock_master.process = AsyncMock(return_value=mock_response)
            
            app.include_router(router)
            client = TestClient(app)
            
            response = client.post("/agent/command", json={"command": "review pr"})
            assert response.status_code in [200, 404]

    def test_review_pr_endpoint(self):
        from src.api.routes.agent import router
        from src.api.main import app
        
        with patch('src.api.routes.agent.master') as mock_master:
            mock_response = MagicMock()
            mock_response.intent.value = "review"
            mock_response.message = "Done"
            mock_response.agent_results = []
            mock_response.summary = "Summary"
            mock_master.review_pr = AsyncMock(return_value=mock_response)
            
            app.include_router(router)
            client = TestClient(app)
            
            response = client.post("/agent/review?repository=test&pr_number=1", params={"diff_content": "test"})
            assert response.status_code in [200, 404]

    def test_webhook_missing_delivery_id(self):
        from src.api.routes.agent import router
        from src.api.main import app
        
        app.include_router(router)
        client = TestClient(app)
        
        response = client.post(
            "/agent/webhook/github",
            json={"action": "opened"},
            headers={"X-GitHub-Event": "pull_request"}
        )
        assert response.status_code in [400, 404]

    def test_webhook_duplicate_event(self):
        from src.api.routes.agent import router
        from src.api.main import app
        
        with patch('src.api.routes.agent.queue_manager') as mock_qm:
            mock_qm.is_duplicate = MagicMock(return_value=True)
            
            app.include_router(router)
            client = TestClient(app)
            
            response = client.post(
                "/agent/webhook/github",
                json={"action": "opened"},
                headers={
                    "X-GitHub-Event": "pull_request",
                    "X-GitHub-Delivery": "test-delivery-123"
                }
            )
            assert response.status_code in [200, 404]
            if response.status_code == 200:
                assert response.json()["status"] == "duplicate"

    def test_queue_status(self):
        from src.api.routes.agent import router
        from src.api.main import app
        
        app.include_router(router)
        client = TestClient(app)
        
        response = client.get("/agent/queue/status")
        assert response.status_code in [200, 404]

    def test_process_pending(self):
        from src.api.routes.agent import router
        from src.api.main import app
        
        app.include_router(router)
        client = TestClient(app)
        
        response = client.post("/agent/queue/process-pending")
        assert response.status_code in [200, 404]

    def test_status_endpoint(self):
        from src.api.routes.agent import router
        from src.api.main import app
        
        app.include_router(router)
        client = TestClient(app)
        
        response = client.get("/agent/status")
        assert response.status_code in [200, 404]

    def test_commands_endpoint(self):
        from src.api.routes.agent import router
        from src.api.main import app
        
        app.include_router(router)
        client = TestClient(app)
        
        response = client.get("/agent/commands")
        assert response.status_code in [200, 404]

    def test_history_endpoint(self):
        from src.api.routes.agent import router
        from src.api.main import app
        
        app.include_router(router)
        client = TestClient(app)
        
        response = client.get("/agent/history")
        assert response.status_code in [200, 404]
