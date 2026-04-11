"""Unit tests for Telegram implementation behavior and validation."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from chat_client_api import Channel, Message
from telegram_client_impl.client import TelegramClient, get_client_impl
from telegram_client_impl.config import TelegramClientConfig
from telegram_client_impl.errors import TelegramMappingError
from telegram_client_impl.mappers import to_channel, to_message
from telegram_client_impl.opaque_ids import (
    encode_telegram_message_id,
    parse_telegram_message_id,
)

EXPECTED_MESSAGE_COUNT = 2


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
        client._client = tele_client

        # send_message
        tele_client.send_message.return_value = object()
        mock_msg = MagicMock(spec=Message)
        mock_to_message.return_value = mock_msg
        result = client.send_message(channel_id="123", text="hello")
        mock_ensure.assert_called()
        tele_client.send_message.assert_called_with(123, "hello")
        assert result is mock_msg

        # get_messages
        tele_client.iter_messages.return_value = [
            object(),
            object(),
        ]
        mock_to_message.reset_mock()
        messages = client.get_messages(
            channel_id="123",
            limit=EXPECTED_MESSAGE_COUNT,
        )
        tele_client.iter_messages.assert_called_with(
            123,
            limit=EXPECTED_MESSAGE_COUNT,
        )
        assert mock_to_message.call_count == EXPECTED_MESSAGE_COUNT
        assert len(messages) == EXPECTED_MESSAGE_COUNT

        # delete_message
        tele_client.delete_messages.reset_mock()
        client.delete_message(message_id="123:5")
        tele_client.delete_messages.assert_called_with(123, [5])

        # get_channels
        tele_client.get_dialogs.return_value = [object()]
        mock_channel = MagicMock(spec=Channel)
        mock_to_channel.return_value = mock_channel
        channels = client.get_channels()
        tele_client.get_dialogs.assert_called_once()
        mock_to_channel.assert_called_once()
        assert channels == [mock_channel]

        # get_channel
        tele_client.get_entity.return_value = object()
        mock_to_channel.return_value = mock_channel
        ch = client.get_channel("99")
        tele_client.get_entity.assert_called_with(99)
        assert ch is mock_channel

        # get_message
        tele_client.get_messages.return_value = object()
        mock_to_message.return_value = mock_msg
        msg = client.get_message("123:7")
        tele_client.get_messages.assert_called_with(123, ids=7)
        assert msg is mock_msg


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
    tele.get_entity.side_effect = OSError("network")
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
    with (
        patch.object(client, "_ensure_connected"),
        patch.object(
            client,
            "_get_client",
            return_value=tele,
        ),
    ):
        tele.get_messages.return_value = []
        with pytest.raises(ValueError, match="Message not found"):
            client.get_message("1:2")

        tele.get_messages.return_value = None
        with pytest.raises(ValueError, match="Message not found"):
            client.get_message("1:2")

        tele.get_messages.return_value = [None]
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
    tele.delete_messages.side_effect = OSError("denied")
    with (
        patch.object(client, "_ensure_connected"),
        patch.object(client, "_get_client", return_value=tele),
        pytest.raises(ValueError, match="Failed to delete message"),
    ):
        client.delete_message("1:2")
