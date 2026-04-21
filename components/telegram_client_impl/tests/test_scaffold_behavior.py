"""Unit tests for Telegram implementation behavior and validation."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from chat_client_api import Channel, Message
from telegram_client_impl.client import TelegramClient, get_client_impl
from telegram_client_impl.config import TelegramClientConfig
from telegram_client_impl.errors import (
    TelegramAuthError,
    TelegramClientError,
    TelegramMappingError,
)
from telegram_client_impl.mappers import to_channel, to_message
from telegram_client_impl.opaque_ids import (
    encode_telegram_message_id,
    parse_telegram_message_id,
)
from telegram_client_impl.telethon_async import run_coroutine

EXPECTED_MESSAGE_COUNT = 2


class _AsyncIter:
    """Minimal async iterator for mocking ``iter_messages``."""

    def __init__(self, items: list[object]) -> None:
        self._it = iter(items)

    def __aiter__(self) -> _AsyncIter:
        return self

    async def __anext__(self) -> object:
        try:
            return next(self._it)
        except StopIteration as exc:
            raise StopAsyncIteration from exc


def _client() -> TelegramClient:
    """Build a client with minimal, non-empty config."""
    config = TelegramClientConfig(api_id="1", api_hash="hash", bot_token="token")
    return TelegramClient(config=config)


def test_client_methods_delegate_to_telethon() -> None:
    """Client methods call through to the Telethon client and mappers."""
    client = _client()

    with (
        patch.object(client, "_ensure_connected") as mock_ensure,
        patch(
            "telegram_client_impl.client.to_message",
        ) as mock_to_message,
        patch(
            "telegram_client_impl.client.to_channel",
        ) as mock_to_channel,
        ):
        # Arrange Telethon client on the instance.
        tele_client = MagicMock()
        tele_client.delete_messages = AsyncMock()
        client._client = tele_client
        target = object()
        client._entity_cache["123"] = target

        # send_message
        tele_client.send_message = AsyncMock(return_value=object())
        mock_msg = MagicMock(spec=Message)
        mock_to_message.return_value = mock_msg
        result = client.send_message(channel_id="123", text="hello")
        mock_ensure.assert_called()
        tele_client.send_message.assert_called_with(target, "hello")
        assert result is mock_msg

        # get_messages
        tele_client.iter_messages.return_value = _AsyncIter([object(), object()])
        mock_to_message.reset_mock()
        messages = client.get_messages(
            channel_id="123",
            limit=EXPECTED_MESSAGE_COUNT,
        )
        tele_client.iter_messages.assert_called_with(
            target,
            limit=EXPECTED_MESSAGE_COUNT,
        )
        assert mock_to_message.call_count == EXPECTED_MESSAGE_COUNT
        assert len(messages) == EXPECTED_MESSAGE_COUNT

        # delete_message
        tele_client.delete_messages.reset_mock()
        client.delete_message(message_id="123:5")
        tele_client.delete_messages.assert_called_with(target, [5])

        # get_channels
        tele_client.get_dialogs = AsyncMock(return_value=[object()])
        mock_channel = MagicMock(spec=Channel)
        mock_to_channel.return_value = mock_channel
        channels = client.get_channels()
        tele_client.get_dialogs.assert_called_once()
        mock_to_channel.assert_called_once()
        assert channels == [mock_channel]

        # get_channel
        client._entity_cache["99"] = object()
        mock_to_channel.return_value = mock_channel
        ch = client.get_channel("99")
        assert ch is mock_channel

        # get_message
        tele_client.get_messages = AsyncMock(return_value=object())
        mock_to_message.return_value = mock_msg
        msg = client.get_message("123:7")
        tele_client.get_messages.assert_called_with(target, ids=7)
        assert msg is mock_msg


def test_client_resolves_dialog_entity_for_operations() -> None:
    """Bare IDs from listed dialogs are resolved back to Telethon entities."""
    client = _client()

    with patch.object(client, "_ensure_connected"):
        entity = SimpleNamespace(id=123, title="Test Group", broadcast=False)
        dialog = SimpleNamespace(entity=entity)
        tele_client = MagicMock()
        tele_client.get_dialogs = AsyncMock(return_value=[dialog])
        tele_client.send_message = AsyncMock(return_value=object())
        client._client = tele_client

        with patch("telegram_client_impl.client.to_message") as mock_to_message:
            mock_msg = MagicMock(spec=Message)
            mock_to_message.return_value = mock_msg

            result = client.send_message(channel_id="123", text="hello")

        tele_client.get_dialogs.assert_called_once()
        tele_client.send_message.assert_called_once_with(entity, "hello")
        assert result is mock_msg


def test_bot_mode_send_does_not_require_dialog_listing() -> None:
    """Bot-token fallback remains send-only and avoids GetDialogsRequest."""
    client = _client()

    with patch.object(client, "_ensure_connected"):
        tele_client = MagicMock()
        tele_client.get_dialogs = AsyncMock(side_effect=AssertionError)
        tele_client.send_message = AsyncMock(return_value=object())
        client._client = tele_client
        client._bot_mode = True

        with patch("telegram_client_impl.client.to_message") as mock_to_message:
            mock_msg = MagicMock(spec=Message)
            mock_to_message.return_value = mock_msg

            result = client.send_message(channel_id="123", text="hello")

        tele_client.get_dialogs.assert_not_called()
        tele_client.send_message.assert_called_once_with(123, "hello")
        assert result is mock_msg


def test_bot_mode_read_operations_fail_with_clear_error() -> None:
    """Read/list operations fail before Telethon bot-only API restrictions."""
    client = _client()
    client._bot_mode = True

    with patch.object(client, "_ensure_connected"):
        with pytest.raises(TelegramClientError, match="bot-token mode"):
            client.get_channels()
        with pytest.raises(TelegramClientError, match="bot-token mode"):
            client.get_messages(channel_id="123")


def test_invalid_session_string_does_not_fallback_to_bot() -> None:
    """A configured user session must be valid; bot fallback is send-only mode."""
    config = TelegramClientConfig(
        api_id="1",
        api_hash="hash",
        bot_token="token",
        session_string="invalid",
    )
    client = TelegramClient(config=config)
    tele_client = MagicMock()
    tele_client.is_connected.return_value = True
    tele_client.is_user_authorized = AsyncMock(return_value=False)
    tele_client.sign_in = AsyncMock()
    client._client = tele_client

    with pytest.raises(TelegramAuthError, match="TELEGRAM_SESSION_STRING"):
        run_coroutine(client._async_start_session())

    tele_client.sign_in.assert_not_called()


def test_client_input_validation() -> None:
    """Input guards execute before scaffold exceptions."""
    client = _client()

    with pytest.raises(ValueError, match="channel_id must be non-empty"):
        client.send_message(channel_id="", text="hello")
    with pytest.raises(ValueError, match="limit must be > 0"):
        client.get_messages(channel_id="ch-1", limit=0)
    with pytest.raises(ValueError, match="message_id must be non-empty"):
        client.delete_message(message_id="")
    with pytest.raises(ValueError, match="Invalid message_id format"):
        client.delete_message(message_id="no-separator")


def test_opaque_message_id_helpers() -> None:
    """Opaque ids use chat_id:telegram_message_id with split(':', 1) semantics."""
    encoded = encode_telegram_message_id(chat_id="-100", telegram_message_id=42)
    assert encoded == "-100:42"
    assert parse_telegram_message_id("-100:42") == (-100, 42)
    with pytest.raises(ValueError, match="Invalid message_id format"):
        parse_telegram_message_id("nocolon")
    with pytest.raises(ValueError, match="must be non-empty"):
        parse_telegram_message_id("")
    with pytest.raises(ValueError, match="empty chat_id"):
        parse_telegram_message_id(":1")
    with pytest.raises(ValueError, match="must be integers"):
        parse_telegram_message_id("x:1")
    with pytest.raises(ValueError, match="chat_id must be non-empty"):
        encode_telegram_message_id(chat_id="", telegram_message_id=1)


def test_get_channel_not_found_wraps_errors() -> None:
    """get_channel raises ValueError when get_entity fails."""
    client = _client()
    tele = MagicMock()
    tele.get_dialogs = AsyncMock(return_value=[])
    tele.get_entity = AsyncMock(side_effect=OSError("network"))
    with (
        patch.object(client, "_ensure_connected"),
        patch.object(client, "_get_client", return_value=tele),
        pytest.raises(ValueError, match="Channel not found"),
    ):
        client.get_channel("99")


def test_get_message_not_found_variants() -> None:
    """get_message raises ValueError when Telethon returns no message."""
    client = _client()
    tele = MagicMock()
    target = object()
    client._entity_cache["1"] = target
    with (
        patch.object(client, "_ensure_connected"),
        patch.object(
            client,
            "_get_client",
            return_value=tele,
        ),
    ):
        tele.get_messages = AsyncMock(return_value=[])
        with pytest.raises(ValueError, match="Message not found"):
            client.get_message("1:2")

        tele.get_messages = AsyncMock(return_value=None)
        with pytest.raises(ValueError, match="Message not found"):
            client.get_message("1:2")

        tele.get_messages = AsyncMock(return_value=[None])
        with pytest.raises(ValueError, match="Message not found"):
            client.get_message("1:2")


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


def test_to_message_rejects_unresolved_peer() -> None:
    """Do not emit opaque ids with an empty chat segment (parser would reject them)."""
    peer = SimpleNamespace(channel_id=None, chat_id=None, user_id=None)
    raw_message = SimpleNamespace(
        id=1,
        sender_id=1,
        peer_id=peer,
        date=datetime(2024, 1, 1, tzinfo=UTC),
        message="x",
    )
    with pytest.raises(TelegramMappingError, match="no channel_id"):
        to_message(raw_message)


def test_mapper_positive_channel_and_message() -> None:
    """Mappers convert Telethon-like objects into shared dataclasses."""
    # Fake Telethon channel entity via SimpleNamespace with required attributes.
    channel_entity = SimpleNamespace(id=42, title="My Channel", broadcast=True)
    channel = to_channel(channel_entity)
    assert channel.channel_id == "42"
    assert channel.name == "My Channel"
    assert channel.channel_type == "channel"
    assert channel.is_private is False

    # Fake Telethon message-like object with a peer namespace.
    peer = SimpleNamespace(channel_id=99, chat_id=None, user_id=None)
    msg_date = datetime(2024, 1, 1, tzinfo=UTC)
    raw_message = SimpleNamespace(
        id=7,
        sender_id=123,
        peer_id=peer,
        date=msg_date,
        message="hi",
    )

    message = to_message(raw_message)
    assert message.message_id == "99:7"
    assert message.channel == "99"
    assert message.sender == "123"
    assert message.timestamp == msg_date.isoformat()
    assert message.text == "hi"


def test_get_client_impl_uses_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Factory reads environment variables through TelegramClientConfig.from_env."""
    monkeypatch.setenv("TELEGRAM_API_ID", "123")
    monkeypatch.setenv("TELEGRAM_API_HASH", "abc")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "token")
    monkeypatch.setenv("TELEGRAM_INTERACTIVE", "1")

    client = get_client_impl()

    assert isinstance(client, TelegramClient)
    assert client._config.interactive is True


def test_delete_message_valueerror_on_rpc_error() -> None:
    """delete_message surfaces RPC failures as ValueError."""
    client = _client()
    tele = MagicMock()
    tele.delete_messages = AsyncMock(side_effect=OSError("denied"))
    client._entity_cache["1"] = object()
    with (
        patch.object(client, "_ensure_connected"),
        patch.object(client, "_get_client", return_value=tele),
        pytest.raises(ValueError, match="Failed to delete message"),
    ):
        client.delete_message("1:2")
