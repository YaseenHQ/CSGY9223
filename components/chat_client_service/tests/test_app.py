"""Tests for chat_client_service FastAPI scaffold endpoints."""

from fastapi.testclient import TestClient

from chat_client_service.app import app

client = TestClient(app)


def test_health_endpoint() -> None:
    """Health endpoint returns 200 with expected payload."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_auth_login_scaffold() -> None:
    """Auth login endpoint returns placeholder redirect details."""
    response = client.get("/auth/login")
    assert response.status_code == 200
    body = response.json()
    assert body["authorization_url"] == "https://oauth.telegram.org/auth"
    assert body["state"] == "scaffold-state"


def test_auth_callback_scaffold() -> None:
    """Auth callback endpoint echoes optional code and state."""
    response = client.get("/auth/callback?code=abc&state=xyz")
    assert response.status_code == 200
    assert response.json() == {
        "detail": "OAuth callback scaffold endpoint.",
        "code": "abc",
        "state": "xyz",
    }


def test_chat_endpoints_are_scaffold_not_implemented() -> None:
    """Core chat endpoints are present and return scaffold 501 responses."""
    send_response = client.post(
        "/chat/messages",
        json={"channel_id": "ch-1", "text": "hello"},
    )
    get_response = client.get("/chat/messages?channel_id=ch-1&max_results=5")
    delete_response = client.delete("/chat/messages/msg-1?channel_id=ch-1")
    channels_response = client.get("/chat/channels")

    assert send_response.status_code == 501
    assert get_response.status_code == 501
    assert delete_response.status_code == 501
    assert channels_response.status_code == 501
