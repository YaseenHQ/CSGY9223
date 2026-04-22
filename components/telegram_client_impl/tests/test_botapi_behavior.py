"""Unit tests for Telegram Bot API implementation behavior and validation."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import TYPE_CHECKING

import httpx
import pytest

from telegram_client_impl.client import TelegramClient, get_client_impl
from telegram_client_impl.config import TelegramClientConfig
from telegram_client_impl.errors import (
    TelegramAuthError,
    TelegramClientError,
    TelegramMappingError,
)
from telegram_client_impl.mappers import to_channel, to_message
from telegram_client_impl.message import TelegramMessage, get_message_impl
from telegram_client_impl.store import get_store, record_update

EXPECTED_MESSAGE_COUNT = 2

if TYPE_CHECKING:
    from collections.abc import Generator


@pytest.fixture(autouse=True)
def isolated_store(monkeypatch: pytest.MonkeyPatch) -> Generator[None, None, None]:
    """Use an in-memory store for Bot API implementation tests."""
    monkeypatch.setenv("CHAT_CLIENT_STORE_PATH", ":memory:")
    get_store().clear()
    yield
    get_store().clear()


def _client(handler: httpx.MockTransport) -> TelegramClient:
    """Build a Bot API client using a fake HTTP transport."""
    get_store().clear()
    http_client = httpx.Client(
        base_url="https://api.telegram.org/bottoken",
        transport=handler,
    )
    config = TelegramClientConfig(bot_token="token")
    return TelegramClient(config=config, http_client=http_client)


def _raw_message(*, message_id: int = 5, text: str = "hello") -> dict[str, object]:
    """Build a Bot API message fixture."""
    return {
        "message_id": message_id,
        "from": {"id": 100, "first_name": "Alice"},
        "chat": {"id": 123, "title": "OSSHWBOTTEST", "type": "group"},
        "date": 1_800_000_000,
        "text": text,
    }


def test_client_methods_use_bot_api_and_store_observed_state() -> None:
    """Client methods call Bot API and read bot-observed local state."""
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path.endswith("/sendMessage"):
            return httpx.Response(
                200,
                json={"ok": True, "result": _raw_message(message_id=5)},
                request=request,
            )
        if request.url.path.endswith("/deleteMessage"):
            return httpx.Response(
                200,
                json={"ok": True, "result": True},
                request=request,
            )
        return httpx.Response(404, json={"ok": False}, request=request)

    client = _client(httpx.MockTransport(handler))

    sent = client.send_message(channel_id="123", text="hello")
    assert sent.id == "5"
    assert sent.channel_id == "123"

    messages = list(client.get_messages("123", limit=EXPECTED_MESSAGE_COUNT))
    assert len(messages) == 1
    assert messages[0].text == "hello"
    assert messages[0].message_id == "5"
    assert messages[0].channel == "123"
    assert client.get_message("123:5").text == "hello"

    channels = list(client.get_channels())
    assert len(channels) == 1
    assert channels[0].name == "OSSHWBOTTEST"
    assert channels[0].channel_id == "123"
    assert channels[0].is_private is False
    assert client.get_channel("123").name == "OSSHWBOTTEST"

    shared_messages = client.get_messages("123", 1, "ignored")
    assert shared_messages[0].id == "5"

    client.delete_message(message_id="123:5")
    assert list(client.get_messages("123")) == []

    assert [request.url.path.rsplit("/", 1)[-1] for request in requests] == [
        "sendMessage",
        "deleteMessage",
    ]


def test_client_requires_bot_token() -> None:
    """Bot API client fails fast without service-owned bot credentials."""
    client = TelegramClient(config=TelegramClientConfig(bot_token=None))

    with pytest.raises(TelegramAuthError, match="TELEGRAM_BOT_TOKEN"):
        list(client.get_channels())


def test_bot_api_error_payload_raises_client_error() -> None:
    """Bot API ok=false responses surface as client errors."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"ok": False, "description": "chat not found"},
            request=request,
        )

    client = _client(httpx.MockTransport(handler))

    with pytest.raises(TelegramClientError, match="chat not found"):
        client.send_message(channel_id="123", text="hello")


def test_bot_api_error_preserves_response_metadata() -> None:
    """Bot API error_code and parameters remain available to callers."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            429,
            json={
                "ok": False,
                "error_code": 429,
                "description": "Too Many Requests",
                "parameters": {"retry_after": 3},
            },
            request=request,
        )

    client = _client(httpx.MockTransport(handler))

    with pytest.raises(TelegramClientError) as exc_info:
        client.send_message(channel_id="123", text="hello")

    assert exc_info.value.method == "sendMessage"
    assert exc_info.value.error_code == 429
    assert exc_info.value.parameters == {"retry_after": 3}


def test_bot_api_non_object_result_raises_client_error() -> None:
    """SendMessage requires a message object in the Bot API result."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"ok": True, "result": True}, request=request)

    client = _client(httpx.MockTransport(handler))

    with pytest.raises(TelegramClientError, match="missing message"):
        client.send_message(channel_id="123", text="hello")


def test_webhook_update_records_message_for_reads() -> None:
    """Webhook-style updates populate the bot-observed read model."""
    get_store().clear()

    record_update({"update_id": 1, "message": _raw_message(message_id=8, text="seen")})

    config = TelegramClientConfig(bot_token="token")
    client = TelegramClient(config=config, http_client=httpx.Client())
    messages = list(client.get_messages("123", limit=1))
    channels = list(client.get_channels())

    assert messages[0].id == "8"
    assert messages[0].text == "seen"
    assert channels[0].id == "123"


def test_webhook_records_edited_channel_post_sender_chat() -> None:
    """Edited channel posts without from are stored with sender_chat fallback."""
    record_update(
        {
            "update_id": 1,
            "edited_channel_post": {
                "message_id": 0,
                "sender_chat": {"id": -1001, "title": "Channel"},
                "chat": {"id": -1001, "title": "Channel", "type": "channel"},
                "date": 1_800_000_000,
                "text": "edited",
            },
        }
    )

    messages = get_store().list_messages(channel_id="-1001", max_results=1)

    assert messages[0].id == "0"
    assert messages[0].sender == "-1001"
    assert messages[0].text == "edited"


def test_webhook_records_bot_membership_chat() -> None:
    """Bot membership updates make newly added chats visible before messages."""
    record_update(
        {
            "update_id": 1,
            "my_chat_member": {
                "from": {"id": 100},
                "chat": {"id": -123, "title": "OSSHWBOTTEST", "type": "group"},
                "date": 1_800_000_000,
                "old_chat_member": {"status": "left"},
                "new_chat_member": {"status": "member"},
            },
        }
    )

    channels = get_store().list_channels()

    assert channels[0].id == "-123"
    assert channels[0].name == "OSSHWBOTTEST"
    assert get_store().user_can_access(telegram_id="100", channel_id="-123") is True


def test_client_can_check_membership_with_bot_api() -> None:
    """Access checks use Bot API getChatMember when local state is missing."""

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/getChatMember")
        return httpx.Response(
            200,
            json={"ok": True, "result": {"status": "member"}},
            request=request,
        )

    client = _client(httpx.MockTransport(handler))

    assert client.user_can_access_channel(user_id="100", channel_id="123") is True
    assert (
        client.user_can_access_channel(user_id="not-numeric", channel_id="123") is False
    )


def test_client_input_validation() -> None:
    """Input guards execute before Bot API operations."""
    client = TelegramClient(config=TelegramClientConfig(bot_token="token"))

    with pytest.raises(ValueError, match="channel_id must be non-empty"):
        client.send_message(channel_id="", text="hello")
    with pytest.raises(ValueError, match="text must be <= 4096 characters"):
        client.send_message(channel_id="ch-1", text="x" * 4097)
    with pytest.raises(ValueError, match="limit must be > 0"):
        list(client.get_messages(channel_id="ch-1", limit=0))
    with pytest.raises(ValueError, match="message_id must be non-empty"):
        client.delete_message(message_id="", channel_id="ch-1")


def test_message_factory_validation_and_construction() -> None:
    """Message factory validates shape and constructs TelegramMessage."""
    with pytest.raises(ValueError, match="msg_id must be non-empty"):
        get_message_impl(msg_id="", raw_data="{}")
    with pytest.raises(ValueError, match="raw_data must be non-empty"):
        get_message_impl(msg_id="m-1", raw_data="")

    payload = {
        "sender": "alice",
        "channel_id": "ch-1",
        "timestamp": datetime(2024, 1, 1, tzinfo=timezone.utc).isoformat(),
        "text": "hello",
    }
    message = get_message_impl(msg_id="m-1", raw_data=json.dumps(payload))
    assert isinstance(message, TelegramMessage)
    assert message.id == "m-1"
    assert message.sender == "alice"
    assert message.channel_id == "ch-1"
    assert message.text == "hello"


def test_mapper_validation_and_errors() -> None:
    """Mappers validate inputs and raise mapping errors for unsupported types."""
    with pytest.raises(ValueError, match="raw_channel cannot be None"):
        to_channel(None)
    with pytest.raises(ValueError, match="raw_message cannot be None"):
        to_message(None)
    with pytest.raises(TelegramMappingError):
        to_channel(object())
    with pytest.raises(TelegramMappingError):
        to_message(object())


def test_mapper_positive_channel_and_message() -> None:
    """Mappers convert Bot API channel and message dictionaries."""
    channel = to_channel({"id": 42, "title": "My Channel", "type": "channel"})
    assert channel.id == "42"
    assert channel.name == "My Channel"
    assert channel.channel_type == "channel"

    message = to_message(_raw_message(message_id=7, text="hi"))
    assert message.id == "7"
    assert message.sender == "100"
    assert message.channel_id == "123"
    assert message.text == "hi"


def test_get_client_impl_uses_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Factory reads environment variables through TelegramClientConfig.from_env."""
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "token")

    client = get_client_impl(interactive=True)

    assert isinstance(client, TelegramClient)
