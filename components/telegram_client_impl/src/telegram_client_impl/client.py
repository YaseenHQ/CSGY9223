"""Telegram implementation of the shared ``ChatClient`` contract."""

from __future__ import annotations

from telethon.errors import RPCError
from telethon.sync import TelegramClient as _TeleClient

from chat_client_api import Channel, ChatClient, Message
from telegram_client_impl.config import TelegramClientConfig
from telegram_client_impl.errors import TelegramAuthError, TelegramClientError
from telegram_client_impl.mappers import to_channel, to_message
from telegram_client_impl.opaque_ids import parse_telegram_message_id


class TelegramClient(ChatClient):
    """Telegram client backed by Telethon."""

    def __init__(self, *, config: TelegramClientConfig) -> None:
        """Initialize a Telegram client with static configuration."""
        self._config = config
        self._client: _TeleClient | None = None
        self._connected = False

    def _get_client(self) -> _TeleClient:
        """Return the underlying Telethon client (must be connected)."""
        assert self._client is not None
        return self._client

    def send_message(self, channel_id: str, text: str) -> Message:
        """Send a message to a Telegram channel/chat."""
        _require_non_empty(value=channel_id, name="channel_id")
        _require_non_empty(value=text, name="text")
        self._ensure_connected()

        try:
            raw = self._get_client().send_message(int(channel_id), text)
        except Exception as exc:  # pragma: no cover - Telethon-specific error types
            msg = f"Failed to send message: {exc}"
            raise TelegramClientError(msg) from exc

        return to_message(raw)

    def get_messages(
        self,
        channel_id: str,
        limit: int = 10,
        cursor: str | None = None,
    ) -> list[Message]:
        """Retrieve messages from a Telegram channel/chat."""
        del cursor  # Telethon path does not use cursor-based pagination here.
        _require_non_empty(value=channel_id, name="channel_id")
        if limit <= 0:
            msg = "limit must be > 0"
            raise ValueError(msg)

        self._ensure_connected()

        try:
            iterator = self._get_client().iter_messages(int(channel_id), limit=limit)
        except Exception as exc:  # pragma: no cover - Telethon-specific error types
            msg = f"Failed to get messages: {exc}"
            raise TelegramClientError(msg) from exc

        return [to_message(raw) for raw in iterator]

    def delete_message(self, message_id: str) -> None:
        """Delete a message using its opaque id."""
        _require_non_empty(value=message_id, name="message_id")
        chat_id, msg_id = parse_telegram_message_id(message_id)
        self._ensure_connected()

        try:
            self._get_client().delete_messages(chat_id, [msg_id])
        except RPCError as exc:
            msg = f"Failed to delete message: {exc}"
            raise ValueError(msg) from exc
        except Exception as exc:  # pragma: no cover - Telethon-specific error types
            msg = f"Failed to delete message: {exc}"
            raise ValueError(msg) from exc

    def get_channels(self) -> list[Channel]:
        """List available Telegram channels/chats."""
        self._ensure_connected()

        try:
            dialogs = self._get_client().get_dialogs()
        except Exception as exc:  # pragma: no cover - Telethon-specific error types
            msg = f"Failed to retrieve channels: {exc}"
            raise TelegramClientError(msg) from exc

        return [to_channel(dialog) for dialog in dialogs]

    def get_channel(self, channel_id: str) -> Channel:
        """Return a single channel by id."""
        _require_non_empty(value=channel_id, name="channel_id")
        self._ensure_connected()
        try:
            entity = self._get_client().get_entity(int(channel_id))
        except Exception as exc:
            msg = f"Channel not found: {channel_id}"
            raise ValueError(msg) from exc
        return to_channel(entity)

    def get_message(self, message_id: str) -> Message:
        """Fetch a message by opaque id."""
        _require_non_empty(value=message_id, name="message_id")
        chat_id, msg_id = parse_telegram_message_id(message_id)
        self._ensure_connected()

        try:
            fetched = self._get_client().get_messages(chat_id, ids=msg_id)
        except RPCError as exc:
            msg = f"Message not found: {message_id}"
            raise ValueError(msg) from exc
        except Exception as exc:  # pragma: no cover - Telethon-specific error types
            msg = f"Failed to get message: {exc}"
            raise ValueError(msg) from exc

        if fetched is None:
            msg = f"Message not found: {message_id}"
            raise ValueError(msg)
        if isinstance(fetched, list):
            if not fetched:
                msg = f"Message not found: {message_id}"
                raise ValueError(msg)
            raw = fetched[0]
        else:
            raw = fetched
        if raw is None:
            msg = f"Message not found: {message_id}"
            raise ValueError(msg)
        return to_message(raw)

    def _ensure_connected(self) -> None:
        """Ensure the underlying Telethon client is authenticated and connected."""
        if self._connected:
            return

        if (
            self._config.api_id is None
            or self._config.api_hash is None
            or self._config.bot_token is None
        ):
            msg = (
                "TELEGRAM_API_ID, TELEGRAM_API_HASH, and "
                "TELEGRAM_BOT_TOKEN are required"
            )
            raise TelegramAuthError(msg)

        if self._client is None:
            self._client = _TeleClient(
                self._config.session_name,
                int(self._config.api_id),
                self._config.api_hash,
            )

        try:
            self._get_client().start(bot_token=self._config.bot_token)
        except Exception as exc:  # pragma: no cover - Telethon-specific error types
            msg = f"Failed to authenticate Telegram client: {exc}"
            raise TelegramAuthError(msg) from exc

        self._connected = True


def get_client_impl() -> ChatClient:
    """Return a ``ChatClient`` instance (used by ``register_client`` and tests)."""
    config = TelegramClientConfig.from_env()
    return TelegramClient(config=config)


def _require_non_empty(*, value: str, name: str) -> None:
    """Validate required string parameters."""
    if not value:
        msg = f"{name} must be non-empty"
        raise ValueError(msg)
