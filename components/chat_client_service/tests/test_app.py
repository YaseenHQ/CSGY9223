"""Tests for the FastAPI Telegram OIDC/Bot API service."""

from collections.abc import Generator
from unittest.mock import Mock, patch

import pytest
from fastapi.testclient import TestClient

from chat_client_service import oidc
from chat_client_service.app import app
from chat_client_service.oidc import (
    OidcConfig,
    begin_login,
    begin_login_library,
    complete_login,
    complete_login_library,
    decode_app_token,
    issue_app_token,
)
from chat_client_service.routers.auth import get_current_claims, get_oidc_config
from chat_client_service.routers.chat import get_chat_client
from telegram_client_impl.store import get_store


@pytest.fixture(autouse=True)
def clear_overrides_and_store(
    monkeypatch: pytest.MonkeyPatch,
) -> Generator[None, None, None]:
    """Clear FastAPI overrides and process-local bot state around tests."""
    monkeypatch.setenv("CHAT_CLIENT_STORE_PATH", ":memory:")
    app.dependency_overrides.clear()
    get_store().clear()
    yield
    app.dependency_overrides.clear()
    get_store().clear()


@pytest.fixture
def client() -> TestClient:
    """Return a FastAPI test client."""
    return TestClient(app)


def _allow_auth() -> dict[str, str]:
    return {"telegram_id": "42", "username": "alice", "name": "Alice"}


def _message() -> Mock:
    msg = Mock()
    msg.id = "5"
    msg.sender = "42"
    msg.channel_id = "123"
    msg.timestamp = "2026-04-21T00:00:00Z"
    msg.text = "hello"
    return msg


def _channel() -> Mock:
    channel = Mock()
    channel.id = "123"
    channel.name = "OSSHWBOTTEST"
    channel.channel_type = "group"
    return channel


class _MembershipClient:
    """Test double with the Bot API membership-check method."""

    checked = False

    def user_can_access_channel(self, *, user_id: str, channel_id: str) -> bool:
        """Grant access only for the test user's known group."""
        self.checked = True
        return user_id == "42" and channel_id == "123"

    def get_messages(
        self,
        channel_id: str,
        limit: int = 10,
        cursor: str | None = None,
    ) -> list[Mock]:
        """Return a message after the access check succeeds."""
        del cursor
        assert channel_id == "123"
        assert limit == 10
        return [_message()]


def test_health(client: TestClient) -> None:
    """Health endpoint is public."""
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_chat_requires_bearer_token(client: TestClient) -> None:
    """Chat endpoints require local OIDC-derived Bearer auth."""
    response = client.get("/chat/channels")

    assert response.status_code == 401


def test_chat_routes_delegate_to_client(client: TestClient) -> None:
    """Protected chat routes preserve the public endpoint contract."""
    service_client = Mock()
    service_client.send_message.return_value = _message()
    service_client.get_messages.return_value = iter([_message()])
    service_client.get_channels.return_value = iter([_channel()])
    service_client.delete_message.return_value = True
    app.dependency_overrides[get_current_claims] = _allow_auth
    app.dependency_overrides[get_chat_client] = lambda: service_client
    get_store().grant_access(telegram_id="42", channel_id="123")

    send_response = client.post(
        "/chat/messages",
        json={"channel_id": "123", "text": "hello"},
    )
    get_response = client.get("/chat/messages", params={"channel_id": "123"})
    channels_response = client.get("/chat/channels")
    delete_response = client.delete("/chat/messages/5", params={"channel_id": "123"})

    assert send_response.status_code == 200
    assert get_response.status_code == 200
    assert channels_response.status_code == 200
    assert delete_response.status_code == 200
    assert send_response.json()["id"] == "123:5"
    assert channels_response.json()[0]["name"] == "OSSHWBOTTEST"
    assert delete_response.json() == {"success": True}
    service_client.delete_message.assert_called_once_with(message_id="123:5")


def test_chat_delete_accepts_returned_opaque_message_id(client: TestClient) -> None:
    """Delete accepts the opaque id returned by send/get message responses."""
    service_client = Mock()
    service_client.delete_message.return_value = True
    app.dependency_overrides[get_current_claims] = _allow_auth
    app.dependency_overrides[get_chat_client] = lambda: service_client
    get_store().grant_access(telegram_id="42", channel_id="123")

    response = client.delete("/chat/messages/123:5")

    assert response.status_code == 200
    service_client.delete_message.assert_called_once_with(message_id="123:5")


def test_chat_send_rejects_text_over_bot_api_limit(client: TestClient) -> None:
    """The HTTP service enforces Telegram sendMessage's 4096 character limit."""
    service_client = Mock()
    app.dependency_overrides[get_current_claims] = _allow_auth
    app.dependency_overrides[get_chat_client] = lambda: service_client
    get_store().grant_access(telegram_id="42", channel_id="123")

    response = client.post(
        "/chat/messages",
        json={"channel_id": "123", "text": "x" * 4097},
    )

    assert response.status_code == 422
    service_client.send_message.assert_not_called()


def test_chat_route_rejects_unobserved_chat(client: TestClient) -> None:
    """Authenticated users cannot operate on chats not linked to their identity."""
    service_client = Mock()
    app.dependency_overrides[get_current_claims] = _allow_auth
    app.dependency_overrides[get_chat_client] = lambda: service_client

    response = client.get("/chat/messages", params={"channel_id": "999"})

    assert response.status_code == 403
    service_client.get_messages.assert_not_called()


def test_chat_route_checks_bot_membership_when_not_cached(client: TestClient) -> None:
    """Access can be proven with Bot API membership if no webhook grant exists."""
    service_client = _MembershipClient()
    app.dependency_overrides[get_current_claims] = _allow_auth
    app.dependency_overrides[get_chat_client] = lambda: service_client

    response = client.get("/chat/messages", params={"channel_id": "123"})

    assert response.status_code == 200
    assert service_client.checked is True
    assert get_store().user_can_access(telegram_id="42", channel_id="123") is True


def test_chat_route_me_alias_targets_authenticated_user(client: TestClient) -> None:
    """channel_id=me resolves to the logged-in user's direct bot chat."""
    service_client = Mock()
    service_client.send_message.return_value = _message()
    app.dependency_overrides[get_current_claims] = _allow_auth
    app.dependency_overrides[get_chat_client] = lambda: service_client
    get_store().grant_access(telegram_id="42", channel_id="42")

    response = client.post(
        "/chat/messages",
        json={"channel_id": "me", "text": "hello"},
    )

    assert response.status_code == 200
    service_client.send_message.assert_called_once_with("42", "hello")


def test_chat_route_errors_return_500(client: TestClient) -> None:
    """Provider failures are translated into HTTP 500 responses."""
    service_client = Mock()
    service_client.get_channels.side_effect = RuntimeError("provider failed")
    app.dependency_overrides[get_current_claims] = _allow_auth
    app.dependency_overrides[get_chat_client] = lambda: service_client
    get_store().grant_access(telegram_id="42", channel_id="123")

    response = client.get("/chat/channels")

    assert response.status_code == 500
    assert response.json()["detail"] == "provider failed"


def test_telegram_webhook_records_update(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Webhook updates become bot-observed reads."""
    monkeypatch.delenv("TELEGRAM_WEBHOOK_SECRET", raising=False)

    response = client.post(
        "/telegram/webhook",
        json={
            "update_id": 1,
            "message": {
                "message_id": 9,
                "from": {"id": 42},
                "chat": {"id": 123, "title": "OSSHWBOTTEST", "type": "group"},
                "date": 1_800_000_000,
                "text": "seen",
            },
        },
    )

    assert response.status_code == 204
    stored = get_store().list_messages(channel_id="123", max_results=1)
    assert stored[0].text == "seen"


def test_telegram_webhook_checks_secret(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Webhook secret blocks non-Telegram callers when configured."""
    monkeypatch.setenv("TELEGRAM_WEBHOOK_SECRET", "secret")
    payload = {
        "update_id": 1,
        "message": {
            "message_id": 9,
            "from": {"id": 42},
            "chat": {"id": 123, "title": "OSSHWBOTTEST", "type": "group"},
            "date": 1_800_000_000,
            "text": "seen",
        },
    }

    bad_response = client.post("/telegram/webhook", json=payload)
    good_response = client.post(
        "/telegram/webhook",
        json=payload,
        headers={"X-Telegram-Bot-Api-Secret-Token": "secret"},
    )

    assert bad_response.status_code == 401
    assert good_response.status_code == 204


def test_auth_login_serves_telegram_login_page(client: TestClient) -> None:
    """Login page fallback works when no OIDC client secret is configured."""
    config = OidcConfig(
        client_id="123",
        client_secret=None,
        service_base_url="https://example.com",
        app_session_secret="app-secret",
    )
    app.dependency_overrides[get_oidc_config] = lambda: config

    response = client.get("/auth/login")

    assert response.status_code == 200
    assert "https://oauth.telegram.org/auth?" in response.text
    assert 'response_type: "post_message"' in response.text
    assert "result.id_token" in response.text
    assert 'const origin = "https://example.com";' in response.text
    assert "openid profile telegram:bot_access" in response.text


def test_auth_login_code_flow_redirects_to_telegram_oidc(
    client: TestClient,
) -> None:
    """Explicit code flow starts the Telegram OIDC Authorization Code Flow."""
    config = OidcConfig(
        client_id="client-id",
        client_secret="secret",
        service_base_url="https://example.com",
        app_session_secret="app-secret",
    )
    app.dependency_overrides[get_oidc_config] = lambda: config

    response = client.get(
        "/auth/login",
        params={"flow": "code"},
        follow_redirects=False,
    )

    assert response.status_code == 302
    location = response.headers["location"]
    assert location.startswith("https://oauth.telegram.org/auth?")
    assert "response_type=code" in location
    assert "code_challenge_method=S256" in location


def test_auth_login_config_supports_telegram_login_library(
    client: TestClient,
) -> None:
    """Login config returns the client_id and nonce used by Telegram.Login.init."""
    config = OidcConfig(
        client_id="123",
        client_secret=None,
        service_base_url="https://example.com",
        app_session_secret="app-secret",
    )
    app.dependency_overrides[get_oidc_config] = lambda: config

    response = client.get("/auth/login/config")

    assert response.status_code == 200
    assert response.json()["client_id"] == "123"
    assert response.json()["origin"] == "https://example.com"
    assert response.json()["nonce"]


def test_auth_callback_issues_local_token(client: TestClient) -> None:
    """Callback exchanges the OIDC code and returns a service Bearer token."""
    config = OidcConfig(
        client_id="client-id",
        client_secret="secret",
        service_base_url="https://example.com",
        app_session_secret="app-secret",
    )
    app.dependency_overrides[get_oidc_config] = lambda: config
    token = issue_app_token(
        config=config,
        claims={
            "id": 42,
            "sub": "oidc-sub",
            "preferred_username": "alice",
            "name": "Alice",
        },
    )

    with patch(
        "chat_client_service.routers.auth.complete_login",
        return_value=(token, None),
    ):
        response = client.get("/auth/callback", params={"code": "c", "state": "s"})

    assert response.status_code == 200
    assert response.json() == {"access_token": token, "token_type": "bearer"}
    assert get_store().user_can_access(telegram_id="42", channel_id="42") is True


def test_auth_login_library_callback_issues_local_token(client: TestClient) -> None:
    """POST callback verifies Telegram.Login id_token and returns a Bearer token."""
    config = OidcConfig(
        client_id="123",
        client_secret=None,
        service_base_url="https://example.com",
        app_session_secret="app-secret",
    )
    app.dependency_overrides[get_oidc_config] = lambda: config
    _client_id, nonce = begin_login_library(config)

    with patch(
        "chat_client_service.oidc.verify_id_token",
        return_value={
            "id": 42,
            "sub": "oidc-sub",
            "preferred_username": "alice",
            "name": "Alice",
        },
    ):
        response = client.post(
            "/auth/callback",
            json={"id_token": "telegram-id-token", "nonce": nonce},
        )

    assert response.status_code == 200
    claims = decode_app_token(
        config=config,
        token=response.json()["access_token"],
    )
    assert claims is not None
    assert claims["telegram_id"] == "42"


def test_auth_session_flow_authenticates_chat_with_session_header(
    client: TestClient,
) -> None:
    """Adapter-style session auth works without changing chat endpoints."""
    config = OidcConfig(
        client_id="123",
        client_secret=None,
        service_base_url="https://example.com",
        app_session_secret="app-secret",
    )
    app.dependency_overrides[get_oidc_config] = lambda: config
    service_client = Mock()
    service_client.send_message.return_value = _message()
    app.dependency_overrides[get_chat_client] = lambda: service_client

    session_response = client.post("/auth/sessions")
    session_payload = session_response.json()
    session_id = session_payload["session_id"]

    config_response = client.get(
        "/auth/login/config",
        params={"session_id": session_id},
    )
    nonce = config_response.json()["nonce"]

    with patch(
        "chat_client_service.oidc.verify_id_token",
        return_value={
            "id": 42,
            "sub": "oidc-sub",
            "preferred_username": "alice",
            "name": "Alice",
        },
    ):
        callback_response = client.post(
            "/auth/callback",
            json={"id_token": "telegram-id-token", "nonce": nonce},
        )

    status_response = client.get(f"/auth/sessions/{session_id}")
    chat_response = client.post(
        "/chat/messages",
        headers={"X-Session-ID": session_id},
        json={"channel_id": "me", "text": "hello"},
    )

    assert session_response.status_code == 201
    assert session_payload["authenticated"] is False
    assert session_payload["login_url"].endswith(f"/auth/login?session_id={session_id}")
    assert callback_response.status_code == 200
    assert "access_token" in callback_response.json()
    assert status_response.json()["authenticated"] is True
    assert status_response.json()["telegram_id"] == "42"
    assert chat_response.status_code == 200
    service_client.send_message.assert_called_once_with("42", "hello")


def test_auth_session_logout_rejects_session_header(client: TestClient) -> None:
    """Deleting a service auth session invalidates X-Session-ID auth."""
    config = OidcConfig(
        client_id="client-id",
        client_secret="secret",
        service_base_url="https://example.com",
        app_session_secret="app-secret",
    )
    token = issue_app_token(
        config=config,
        claims={"id": 42, "sub": "oidc-sub", "preferred_username": "alice"},
    )
    app.dependency_overrides[get_oidc_config] = lambda: config
    get_store().create_auth_session(session_id="session-1", created_at=1)
    claims = decode_app_token(config=config, token=token)
    assert claims is not None
    get_store().authenticate_session(
        session_id="session-1",
        token=token,
        claims=claims,
    )

    delete_response = client.delete("/auth/sessions/session-1")
    chat_response = client.get(
        "/chat/channels",
        headers={"X-Session-ID": "session-1"},
    )

    assert delete_response.status_code == 200
    assert delete_response.json() == {"success": True}
    assert chat_response.status_code == 401


def test_auth_me_decodes_local_token(client: TestClient) -> None:
    """Issued local tokens authenticate /auth/me."""
    config = OidcConfig(
        client_id="client-id",
        client_secret="secret",
        service_base_url="https://example.com",
        app_session_secret="app-secret",
    )
    token = issue_app_token(
        config=config,
        claims={
            "id": 42,
            "sub": "oidc-sub",
            "preferred_username": "alice",
            "name": "Alice",
        },
    )
    app.dependency_overrides[get_oidc_config] = lambda: config

    response = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    assert response.json()["telegram_id"] == "42"


def test_auth_me_rejects_tampered_token(client: TestClient) -> None:
    """Invalid local Bearer tokens are rejected."""
    config = OidcConfig(
        client_id="client-id",
        client_secret="secret",
        service_base_url="https://example.com",
        app_session_secret="app-secret",
    )
    app.dependency_overrides[get_oidc_config] = lambda: config

    response = client.get("/auth/me", headers={"Authorization": "Bearer bad.token"})

    assert response.status_code == 401


def test_auth_me_rejects_expired_token(client: TestClient) -> None:
    """Expired local Bearer tokens are rejected."""
    config = OidcConfig(
        client_id="client-id",
        client_secret="secret",
        service_base_url="https://example.com",
        app_session_secret="app-secret",
        app_session_ttl_seconds=-1,
    )
    token = issue_app_token(config=config, claims={"sub": "42"})
    app.dependency_overrides[get_oidc_config] = lambda: config

    response = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 401


def test_begin_login_requires_oidc_config() -> None:
    """OIDC startup fails loudly without service-owned Telegram credentials."""
    config = OidcConfig(
        client_id=None,
        client_secret=None,
        service_base_url="https://example.com",
        app_session_secret="app-secret",
    )

    with pytest.raises(ValueError, match="TELEGRAM_BOT_TOKEN"):
        begin_login(config)


def test_oidc_config_derives_login_client_id_from_bot_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Telegram Login defaults to the bot token's numeric bot id."""
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123456:bot-secret")
    monkeypatch.delenv("TELEGRAM_OIDC_CLIENT_ID", raising=False)
    monkeypatch.delenv("APP_SESSION_SECRET", raising=False)

    config = OidcConfig.from_env()

    assert config.client_id == "123456"
    assert config.app_session_secret == "123456:bot-secret"  # noqa: S105


def test_oidc_config_allows_explicit_login_client_id_override(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Explicit Telegram Login client id overrides bot token derivation."""
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123456:bot-secret")
    monkeypatch.setenv("TELEGRAM_OIDC_CLIENT_ID", "client-id")
    monkeypatch.delenv("APP_SESSION_SECRET", raising=False)

    config = OidcConfig.from_env()

    assert config.client_id == "client-id"
    assert config.app_session_secret == "123456:bot-secret"  # noqa: S105


def test_complete_login_exchanges_code_and_issues_token() -> None:
    """OIDC callback exchanges code, verifies id_token, and signs local token."""
    config = OidcConfig(
        client_id="client-id",
        client_secret="secret",
        service_base_url="https://example.com",
        app_session_secret="app-secret",
    )
    _url, state = begin_login(config)

    with (
        patch(
            "chat_client_service.oidc._exchange_code",
            return_value={"id_token": "telegram-id-token"},
        ) as exchange_code,
        patch(
            "chat_client_service.oidc.verify_id_token",
            return_value={
                "id": 42,
                "sub": "oidc-sub",
                "preferred_username": "alice",
                "name": "Alice",
            },
        ) as verify_id_token,
    ):
        token, session_id = complete_login(config=config, code="code", state=state)

    claims = decode_app_token(config=config, token=token)
    assert claims is not None
    assert claims["telegram_id"] == "42"
    assert session_id is None
    exchange_code.assert_called_once()
    verify_id_token.assert_called_once()
    assert verify_id_token.call_args.kwargs["nonce"]


def test_complete_login_library_rejects_bad_nonce() -> None:
    """Telegram.Login callback rejects missing server-generated nonce."""
    config = OidcConfig(
        client_id="client-id",
        client_secret=None,
        service_base_url="https://example.com",
        app_session_secret="app-secret",
    )

    with pytest.raises(ValueError, match="Invalid or expired Telegram Login nonce"):
        complete_login_library(
            config=config,
            id_token="telegram-id-token",
            nonce="missing",
        )


def test_oidc_code_exchange_uses_basic_auth() -> None:
    """Token exchange follows Telegram OIDC client-auth requirements."""
    config = OidcConfig(
        client_id="client-id",
        client_secret="secret",
        service_base_url="https://example.com",
        app_session_secret="app-secret",
    )
    response = Mock()
    response.json.return_value = {"id_token": "telegram-id-token"}
    response.raise_for_status.return_value = None

    with patch("chat_client_service.oidc.httpx.post", return_value=response) as post:
        payload = oidc._exchange_code(
            config=config,
            code="code",
            code_verifier="verifier",
        )

    assert payload == {"id_token": "telegram-id-token"}
    assert post.call_args.kwargs["auth"] == ("client-id", "secret")
    assert "client_secret" not in post.call_args.kwargs["data"]


def test_complete_login_rejects_bad_state() -> None:
    """OIDC callback rejects missing or expired state values."""
    config = OidcConfig(
        client_id="client-id",
        client_secret="secret",
        service_base_url="https://example.com",
        app_session_secret="app-secret",
    )

    with pytest.raises(ValueError, match="Invalid or expired"):
        complete_login(config=config, code="code", state="missing")
