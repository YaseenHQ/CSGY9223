"""Telegram Client scaffold implementing the chat_client_api.Client contract."""

from collections.abc import Iterator

from chat_client_api.channel import Channel
from chat_client_api.client import Client
from chat_client_api.message import Message

from telegram_client_impl.config import TelegramClientConfig


class TelegramClient(Client):
    """Scaffold Telegram client.

    Methods are intentionally unimplemented and raise NotImplementedError.
    """

    def __init__(self, *, config: TelegramClientConfig) -> None:
        """Initialize a Telegram client scaffold with static configuration."""
        self._config = config

    def send_message(self, channel_id: str, text: str) -> Message:
        """Send a message to a Telegram channel/chat."""
        _require_non_empty(value=channel_id, name="channel_id")
        _require_non_empty(value=text, name="text")
        raise NotImplementedError

    def get_messages(
        self, channel_id: str, max_results: int = 10
    ) -> Iterator[Message]:
        """Retrieve messages from a Telegram channel/chat."""
        _require_non_empty(value=channel_id, name="channel_id")
        if max_results <= 0:
            msg = "max_results must be > 0"
            raise ValueError(msg)
        raise NotImplementedError

    def delete_message(self, channel_id: str, message_id: str) -> bool:
        """Delete a message in a Telegram channel/chat."""
        _require_non_empty(value=channel_id, name="channel_id")
        _require_non_empty(value=message_id, name="message_id")
        raise NotImplementedError

    def get_channels(self) -> Iterator[Channel]:
        """List available Telegram channels/chats."""
        raise NotImplementedError


def get_client_impl(*, interactive: bool = False) -> Client:
    """Return the injected client factory implementation."""
    config = TelegramClientConfig.from_env(interactive=interactive)
    return TelegramClient(config=config)


def _require_non_empty(*, value: str, name: str) -> None:
    """Validate required string parameters."""
    if not value:
        msg = f"{name} must be non-empty"
        raise ValueError(msg)
