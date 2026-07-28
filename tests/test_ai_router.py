# tests/test_ai_router.py
"""
Unit tests for AI Manager router and Supervity AI workflow endpoint integration.
"""

from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_ai_chat_success():
    mock_response = AsyncMock()
    mock_response.status_code = 200
    mock_response.text = '{"response": "Ticket processed and escalated successfully."}'

    with patch("httpx.AsyncClient.post", return_value=mock_response):
        response = client.post(
            "/api/ai/chat",
            json={
                "message": "User reports high SLA delay on ticket #123",
                "issue_key": "PROJ-123",
                "reporter_email": "test@example.com",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert "Ticket processed" in data["response"]
        assert data["workflow_id"] == "019f7cc4-552a-7000-8d0f-d226fe29f247"


def test_ai_chat_supervity_stream_parsing():
    mock_response = AsyncMock()
    mock_response.status_code = 200
    mock_response.text = (
        "data: {\"text\": \"Processing request...\"}\n"
        "data: {\"text\": \" Workflow finished.\"}\n"
        "data: [DONE]\n"
    )

    with patch("httpx.AsyncClient.post", return_value=mock_response):
        response = client.post(
            "/api/ai/chat",
            json={"message": "Analyze system performance logs"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "Processing request..." in data["response"]
