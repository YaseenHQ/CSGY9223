"""Tests for Telegram webhook configuration script."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from unittest.mock import Mock, patch

import httpx

from scripts import configure_telegram_webhook

if TYPE_CHECKING:
    import pytest


def test_configure_webhook_sends_supported_update_types(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """SetWebhook payload follows the Bot API webhook configuration contract."""
    webhook_secret = "sec" + "ret"
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "bot-token")
    monkeypatch.setenv("SERVICE_BASE_URL", "https://example.com")
    monkeypatch.setenv("TELEGRAM_WEBHOOK_SECRET", webhook_secret)
    monkeypatch.setenv("TELEGRAM_WEBHOOK_DROP_PENDING_UPDATES", "true")
    response = Mock(spec=httpx.Response)
    response.json.return_value = {"ok": True, "result": True}
    response.raise_for_status.return_value = None

    with patch(
        "scripts.configure_telegram_webhook.httpx.post",
        return_value=response,
    ) as post:
        exit_code = configure_telegram_webhook.main()

    payload: dict[str, Any] = post.call_args.kwargs["json"]
    assert exit_code == 0
    assert payload["url"] == "https://example.com/telegram/webhook"
    assert payload["secret_token"] == webhook_secret
    assert payload["drop_pending_updates"] is True
    assert payload["allowed_updates"] == [
        "message",
        "edited_message",
        "channel_post",
        "edited_channel_post",
        "my_chat_member",
    ]


def test_configure_webhook_allows_update_override(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Deployers can override allowed_updates without editing the script."""
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "bot-token")
    monkeypatch.setenv("SERVICE_BASE_URL", "https://example.com")
    monkeypatch.delenv("TELEGRAM_WEBHOOK_SECRET", raising=False)
    monkeypatch.setenv("TELEGRAM_WEBHOOK_ALLOWED_UPDATES", "message,chat_member")
    response = Mock(spec=httpx.Response)
    response.json.return_value = {"ok": True, "result": True}
    response.raise_for_status.return_value = None

    with patch(
        "scripts.configure_telegram_webhook.httpx.post",
        return_value=response,
    ) as post:
        exit_code = configure_telegram_webhook.main()

    payload: dict[str, Any] = post.call_args.kwargs["json"]
    assert exit_code == 0
    assert "secret_token" not in payload
    assert payload["allowed_updates"] == ["message", "chat_member"]
