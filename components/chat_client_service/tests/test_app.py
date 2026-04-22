"""Tests for chat_client_service FastAPI endpoints."""

from collections.abc import Generator
from typing import Any
from unittest.mock import Mock, patch

import pytest
from fastapi import APIRouter
from fastapi.testclient import TestClient

from chat_client_api import Channel, Message
from chat_client_service.app import app
from chat_client_service.routers.auth import get_current_token
from chat_client_service.routers.chat import get_chat_client

client = TestClient(app, follow_redirects=False)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _message_dto(*, message_id: str = "m-1") -> Message:
    return Message(
        message_id=message_id,
        sender="alice",
        channel="ch-1",
        timestamp="2026-03-20T00:00:00",
        text="hello",
    )


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------


def test_health_endpoint() -> None:
    """Health endpoint returns 200 with expected payload."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_health_request_emits_success_telemetry() -> None:
    """GET /health records latency and marks the request as successful."""
    with patch(
        "chat_client_service.middleware.telemetry._publish_request_metrics"
    ) as publish_metrics:
        response = client.get("/health")

    assert response.status_code == 200
    publish_metrics.assert_called_once()
    kwargs: dict[str, Any] = publish_metrics.await_args.kwargs
    assert kwargs["service"] == "chat_client_service"
    assert kwargs["endpoint"] == "/health"
    assert kwargs["status_code"] == 200
    assert kwargs["success"] == 1
    assert kwargs["failure"] == 0
    assert kwargs["latency_ms"] >= 0


def test_parameterized_route_uses_template_endpoint_dimension(
    mock_chat_client: Mock,
) -> None:
    """Telemetry uses the FastAPI route template instead of the raw request path."""
    mock_chat_client.get_message.return_value = _message_dto(message_id="m-1")

    with patch(
        "chat_client_service.middleware.telemetry._publish_request_metrics"
    ) as publish_metrics:
        response = client.get("/chat/messages/m-1")

    assert response.status_code == 200
    kwargs: dict[str, Any] = publish_metrics.await_args.kwargs
    assert kwargs["endpoint"] == "/chat/messages/{message_id}"
    assert kwargs["status_code"] == 200
    assert kwargs["success"] == 1
    assert kwargs["failure"] == 0


def test_failure_response_emits_failure_telemetry(mock_chat_client: Mock) -> None:
    """HTTP responses with status >= 400 are recorded as failures."""
    mock_chat_client.get_channels.side_effect = RuntimeError("Telegram error")

    with patch(
        "chat_client_service.middleware.telemetry._publish_request_metrics"
    ) as publish_metrics:
        response = client.get("/chat/channels")

    assert response.status_code == 500
    kwargs: dict[str, Any] = publish_metrics.await_args.kwargs
    assert kwargs["endpoint"] == "/chat/channels"
    assert kwargs["status_code"] == 500
    assert kwargs["success"] == 0
    assert kwargs["failure"] == 1


def test_unhandled_exception_still_emits_failure_telemetry() -> None:
    """Unhandled exceptions still publish telemetry before FastAPI returns 500."""
    router = APIRouter()

    @router.get("/telemetry-boom")
    def telemetry_boom() -> None:
        raise RuntimeError("boom")

    app.include_router(router)
    try:
        boom_client = TestClient(app, follow_redirects=False, raise_server_exceptions=False)
        with patch(
            "chat_client_service.middleware.telemetry._publish_request_metrics"
        ) as publish_metrics:
            response = boom_client.get("/telemetry-boom")
    finally:
        app.router.routes.pop()

    assert response.status_code == 500
    kwargs: dict[str, Any] = publish_metrics.await_args.kwargs
    assert kwargs["endpoint"] == "/telemetry-boom"
    assert kwargs["status_code"] == 500
    assert kwargs["success"] == 0
    assert kwargs["failure"] == 1


# ---------------------------------------------------------------------------
# Auth — Telegram Login Widget flow
# ---------------------------------------------------------------------------


def test_auth_login_redirects_to_provider() -> None:
    """GET /auth/login returns 302 to Telegram and sets the CSRF state cookie."""
    response = client.get("/auth/login")
    assert response.status_code == 302
    location = response.headers["location"]
    assert location.startswith("https://oauth.telegram.org/auth?bot_id=")
    assert "return_to=" in location
    assert "state=" not in location  # state is now in cookie, not URL
    assert "oauth_state" in response.cookies


def test_auth_callback_returns_html_bridge() -> None:
    """GET /auth/callback returns the JS bridge page (no params needed)."""
    response = client.get("/auth/callback")
    assert response.status_code == 200
    assert "tgAuthResult" in response.text
    assert "/auth/verify" in response.text


_FAKE_USER = {
    "id": 123456,
    "first_name": "Alice",
    "auth_date": 1700000000,
    "hash": "fakehash",
}


def test_auth_verify_rejects_missing_cookie() -> None:
    """POST /auth/verify returns 400 when no CSRF state cookie is present."""
    fresh = TestClient(app, follow_redirects=False)
    response = fresh.post("/auth/verify", json=_FAKE_USER)
    assert response.status_code == 400
    assert "cookie" in response.json()["detail"].lower()


def test_auth_full_flow_returns_access_token() -> None:
    """Full flow: login → callback page → verify → access_token."""
    login_response = client.get("/auth/login")
    assert login_response.status_code == 302
    assert "oauth_state" in login_response.cookies
    state = login_response.cookies["oauth_state"]

    with patch(
        "chat_client_service.routers.auth._verify_telegram_hash", return_value=True
    ):
        verify_response = client.post("/auth/verify", json=_FAKE_USER)
    assert verify_response.status_code == 200
    body = verify_response.json()

    assert body["state"] == state
    assert body["access_token"] is not None
    assert len(body["access_token"]) >= 43
    assert body["token_type"] == "bearer"


def test_auth_cookie_is_cleared_after_verify() -> None:
    """The CSRF cookie is deleted after a successful verify call."""
    client.get("/auth/login")
    with patch(
        "chat_client_service.routers.auth._verify_telegram_hash", return_value=True
    ):
        client.post("/auth/verify", json=_FAKE_USER)
    # Cookie gone — second verify must fail
    r2 = client.post("/auth/verify", json=_FAKE_USER)
    assert r2.status_code == 400


def test_auth_verify_rejects_invalid_hash() -> None:
    """POST /auth/verify returns 401 when Telegram HMAC check fails."""
    client.get("/auth/login")
    with patch(
        "chat_client_service.routers.auth._verify_telegram_hash", return_value=False
    ):
        response = client.post("/auth/verify", json=_FAKE_USER)
    assert response.status_code == 401


def test_auth_me_requires_valid_token() -> None:
    """GET /auth/me returns 401 without a valid Bearer token."""
    response = client.get("/auth/me")
    assert response.status_code == 401


def test_auth_me_returns_session_data_with_valid_token() -> None:
    """GET /auth/me returns session metadata for an authenticated caller."""
    client.get("/auth/login")
    with patch(
        "chat_client_service.routers.auth._verify_telegram_hash", return_value=True
    ):
        verify_response = client.post("/auth/verify", json=_FAKE_USER)
    token = verify_response.json()["access_token"]

    me_response = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_response.status_code == 200
    assert "token" in me_response.json()


# ---------------------------------------------------------------------------
# Chat — delegate to impl via DI override
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_chat_client() -> Generator[Mock, None, None]:
    """Provide a mock Client wired into the FastAPI dependency system."""
    mock = Mock()
    app.dependency_overrides[get_chat_client] = lambda: mock
    app.dependency_overrides[get_current_token] = lambda: "test-token"
    yield mock
    app.dependency_overrides.pop(get_chat_client, None)
    app.dependency_overrides.pop(get_current_token, None)


def test_send_message_delegates_to_client(mock_chat_client: Mock) -> None:
    """POST /chat/messages delegates to the injected client."""
    mock_chat_client.send_message.return_value = _message_dto()

    response = client.post(
        "/chat/messages", json={"channel_id": "ch-1", "text": "hello"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == "m-1"
    assert body["text"] == "hello"
    mock_chat_client.send_message.assert_called_once_with(
        channel_id="ch-1", text="hello"
    )


def test_get_messages_delegates_to_client(mock_chat_client: Mock) -> None:
    """GET /chat/messages delegates to the injected client."""
    mock_chat_client.get_messages.return_value = [
        _message_dto(message_id="m-1"),
        _message_dto(message_id="m-2"),
    ]

    response = client.get("/chat/messages?channel_id=ch-1&limit=2")

    assert response.status_code == 200
    ids = [m["id"] for m in response.json()]
    assert ids == ["m-1", "m-2"]
    mock_chat_client.get_messages.assert_called_once_with(channel_id="ch-1", limit=2)


def test_get_messages_accepts_generated_client_max_results(
    mock_chat_client: Mock,
) -> None:
    """GET /chat/messages keeps compatibility with generated clients."""
    mock_chat_client.get_messages.return_value = [_message_dto(message_id="m-1")]

    response = client.get("/chat/messages?channel_id=ch-1&max_results=3")

    assert response.status_code == 200
    assert response.json()[0]["id"] == "m-1"
    mock_chat_client.get_messages.assert_called_once_with(channel_id="ch-1", limit=3)


def test_delete_message_delegates_to_client(mock_chat_client: Mock) -> None:
    """DELETE /chat/messages/{id} delegates to the injected client."""
    response = client.delete("/chat/messages/m-1")

    assert response.status_code == 200
    assert response.json() == {"success": True}
    mock_chat_client.delete_message.assert_called_once_with(message_id="m-1")


def test_get_message_delegates_to_client(mock_chat_client: Mock) -> None:
    """GET /chat/messages/{id} delegates to the injected client."""
    mock_chat_client.get_message.return_value = _message_dto(message_id="m-1")

    response = client.get("/chat/messages/m-1")

    assert response.status_code == 200
    assert response.json()["id"] == "m-1"
    mock_chat_client.get_message.assert_called_once_with(message_id="m-1")


def test_get_channels_delegates_to_client(mock_chat_client: Mock) -> None:
    """GET /chat/channels delegates to the injected client."""
    ch = Channel(
        channel_id="ch-1",
        name="general",
        is_private=False,
        channel_type="group",
    )
    mock_chat_client.get_channels.return_value = [ch]

    response = client.get("/chat/channels")

    assert response.status_code == 200
    channels = response.json()
    assert channels[0]["id"] == "ch-1"
    assert channels[0]["name"] == "general"


def test_send_message_returns_500_on_client_error(mock_chat_client: Mock) -> None:
    """POST /chat/messages returns 500 when the client raises an exception."""
    mock_chat_client.send_message.side_effect = RuntimeError("Telegram error")

    response = client.post(
        "/chat/messages", json={"channel_id": "ch-1", "text": "hello"}
    )

    assert response.status_code == 500


def test_get_messages_returns_500_on_client_error(mock_chat_client: Mock) -> None:
    """GET /chat/messages returns 500 when the client raises an exception."""
    mock_chat_client.get_messages.side_effect = RuntimeError("Telegram error")

    response = client.get("/chat/messages?channel_id=ch-1")

    assert response.status_code == 500


def test_delete_message_returns_500_on_client_error(mock_chat_client: Mock) -> None:
    """DELETE /chat/messages/{id} returns 500 when the client raises an exception."""
    mock_chat_client.delete_message.side_effect = RuntimeError("Telegram error")

    response = client.delete("/chat/messages/m-1")

    assert response.status_code == 500


def test_get_message_returns_500_on_client_error(mock_chat_client: Mock) -> None:
    """GET /chat/messages/{id} returns 500 when the client raises an exception."""
    mock_chat_client.get_message.side_effect = RuntimeError("Telegram error")

    response = client.get("/chat/messages/m-1")

    assert response.status_code == 500


def test_get_channels_returns_500_on_client_error(mock_chat_client: Mock) -> None:
    """GET /chat/channels returns 500 when the client raises an exception."""
    mock_chat_client.get_channels.side_effect = RuntimeError("Telegram error")

    response = client.get("/chat/channels")

    assert response.status_code == 500
