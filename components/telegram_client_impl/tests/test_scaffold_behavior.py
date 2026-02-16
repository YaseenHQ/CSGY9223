"""Unit tests for Telegram scaffold placeholders and validation."""

import pytest
from telegram_client_impl.client import TelegramClient, get_client_impl
from telegram_client_impl.config import TelegramClientConfig
from telegram_client_impl.mappers import to_channel, to_message
from telegram_client_impl.message import get_message_impl


def _client() -> TelegramClient:
    """Build a scaffold client with minimal config."""
    config = TelegramClientConfig(api_id=None, api_hash=None, bot_token=None)
    return TelegramClient(config=config)


def test_client_methods_raise_not_implemented() -> None:
    """Scaffold methods raise NotImplementedError after input validation."""
    client = _client()

    with pytest.raises(NotImplementedError):
        client.send_message(channel_id="ch-1", text="hello")
    with pytest.raises(NotImplementedError):
        list(client.get_messages(channel_id="ch-1", max_results=1))
    with pytest.raises(NotImplementedError):
        client.delete_message(channel_id="ch-1", message_id="m-1")
    with pytest.raises(NotImplementedError):
        list(client.get_channels())


def test_client_input_validation() -> None:
    """Input guards execute before scaffold exceptions."""
    client = _client()

    with pytest.raises(ValueError, match="channel_id must be non-empty"):
        client.send_message(channel_id="", text="hello")
    with pytest.raises(ValueError, match="max_results must be > 0"):
        list(client.get_messages(channel_id="ch-1", max_results=0))
    with pytest.raises(ValueError, match="message_id must be non-empty"):
        client.delete_message(channel_id="ch-1", message_id="")


def test_message_factory_scaffold_and_validation() -> None:
    """Message factory validates shape and remains unimplemented."""
    with pytest.raises(ValueError, match="msg_id must be non-empty"):
        get_message_impl(msg_id="", raw_data="{}")
    with pytest.raises(ValueError, match="raw_data must be non-empty"):
        get_message_impl(msg_id="m-1", raw_data="")
    with pytest.raises(NotImplementedError):
        get_message_impl(msg_id="m-1", raw_data="{}")


def test_mapper_scaffold_and_validation() -> None:
    """Mapper placeholders validate inputs and raise scaffold errors."""
    with pytest.raises(ValueError, match="raw_channel cannot be None"):
        to_channel(None)
    with pytest.raises(ValueError, match="raw_message cannot be None"):
        to_message(None)
    with pytest.raises(NotImplementedError):
        to_channel(object())
    with pytest.raises(NotImplementedError):
        to_message(object())


def test_get_client_impl_uses_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Factory reads environment variables through TelegramClientConfig.from_env."""
    monkeypatch.setenv("TELEGRAM_API_ID", "123")
    monkeypatch.setenv("TELEGRAM_API_HASH", "abc")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "token")

    client = get_client_impl(interactive=True)

    assert isinstance(client, TelegramClient)
