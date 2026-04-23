"""Telegram implementation of the shared ``ChatClient`` contract."""

from __future__ import annotations

from telethon import TelegramClient as _TeleClient
from telethon.errors import RPCError
from telethon.sessions import StringSession

from chat_client_api import Channel, ChatClient, Message
from telegram_client_impl.config import TelegramClientConfig
from telegram_client_impl.errors import TelegramAuthError, TelegramClientError
from telegram_client_impl.mappers import to_channel, to_message
from telegram_client_impl.opaque_ids import parse_telegram_message_id
from telegram_client_impl.telethon_async import run_coroutine


class TelegramClient(ChatClient):
    """Telegram client backed by Telethon."""

    def __init__(self, *, config: TelegramClientConfig) -> None:
        """Initialize a Telegram client with static configuration."""
        self._config = config
        self._client: _TeleClient | None = None
        self._connected = False
        self._bot_mode = False
        self._entity_cache: dict[str, object] = {}

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
            target = self._resolve_target(channel_id)
            raw = run_coroutine(self._get_client().send_message(target, text))
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
        self._require_user_session(operation="get_messages")

        async def _collect() -> list[Message]:
            target = await self._resolve_target_async(channel_id)
            return [
                to_message(raw)
                async for raw in self._get_client().iter_messages(
                    target,
                    limit=limit,
                )
            ]

        try:
            return run_coroutine(_collect())
        except Exception as exc:  # pragma: no cover - Telethon-specific error types
            msg = f"Failed to get messages: {exc}"
            raise TelegramClientError(msg) from exc

    def delete_message(self, message_id: str) -> None:
        """Delete a message using its opaque id."""
        _require_non_empty(value=message_id, name="message_id")
        chat_id, msg_id = parse_telegram_message_id(message_id)
        self._ensure_connected()

        try:
            target = self._resolve_target(str(chat_id))
            run_coroutine(self._get_client().delete_messages(target, [msg_id]))
        except RPCError as exc:
            msg = f"Failed to delete message: {exc}"
            raise ValueError(msg) from exc
        except Exception as exc:  # pragma: no cover - Telethon-specific error types
            msg = f"Failed to delete message: {exc}"
            raise ValueError(msg) from exc

    def get_channels(self) -> list[Channel]:
        """List available Telegram channels/chats."""
        self._ensure_connected()
        self._require_user_session(operation="get_channels")

        try:
            dialogs = run_coroutine(self._get_client().get_dialogs())
        except Exception as exc:  # pragma: no cover - Telethon-specific error types
            msg = f"Failed to retrieve channels: {exc}"
            raise TelegramClientError(msg) from exc

        for dialog in dialogs:
            self._cache_dialog_entity(dialog)
        return [to_channel(dialog) for dialog in dialogs]

    def get_channel(self, channel_id: str) -> Channel:
        """Return a single channel by id."""
        _require_non_empty(value=channel_id, name="channel_id")
        self._ensure_connected()
        self._require_user_session(operation="get_channel")
        try:
            target = self._resolve_target(channel_id)
            entity = (
                run_coroutine(self._get_client().get_entity(target))
                if isinstance(target, (int, str))
                else target
            )
        except Exception as exc:
            msg = f"Channel not found: {channel_id}"
            raise ValueError(msg) from exc
        return to_channel(entity)

    def get_message(self, message_id: str) -> Message:
        """Fetch a message by opaque id."""
        _require_non_empty(value=message_id, name="message_id")
        chat_id, msg_id = parse_telegram_message_id(message_id)
        self._ensure_connected()
        self._require_user_session(operation="get_message")

        try:
            target = self._resolve_target(str(chat_id))
            fetched = run_coroutine(self._get_client().get_messages(target, ids=msg_id))
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
            or (self._config.session_string is None and self._config.bot_token is None)
        ):
            msg = (
                "TELEGRAM_API_ID, TELEGRAM_API_HASH, and either "
                "TELEGRAM_SESSION_STRING or TELEGRAM_BOT_TOKEN are required"
            )
            raise TelegramAuthError(msg)

        if self._client is None:
            session = (
                StringSession(self._config.session_string)
                if self._config.session_string
                else self._config.session_name
            )
            self._client = _TeleClient(
                session,
                int(self._config.api_id),
                self._config.api_hash,
            )

        try:
            # Do not use Telethon ``start()`` here: it is synchronous and calls
            # ``self.loop`` (``get_running_loop()``) before returning a coroutine,
            # which breaks under FastAPI's AnyIO worker threads.
            run_coroutine(self._async_start_session())
        except Exception as exc:  # pragma: no cover - Telethon-specific error types
            msg = f"Failed to authenticate Telegram client: {exc}"
            raise TelegramAuthError(msg) from exc

        self._connected = True

    async def _async_start_session(self) -> None:
        """Connect with async Telethon APIs; bot login is only a fallback."""
        client = self._get_client()
        if not client.is_connected():
            await client.connect()
        if await client.is_user_authorized():
            self._bot_mode = False
            return
        if self._config.session_string is not None:
            msg = "TELEGRAM_SESSION_STRING is invalid or expired"
            raise TelegramAuthError(msg)
        if self._config.bot_token is None:
            msg = "TELEGRAM_SESSION_STRING is invalid or expired"
            raise TelegramAuthError(msg)
        await client.sign_in(bot_token=self._config.bot_token)
        self._bot_mode = True

    def _require_user_session(self, *, operation: str) -> None:
        if not self._bot_mode:
            return
        msg = (
            f"{operation} requires TELEGRAM_SESSION_STRING or an authorized "
            "Telegram user session; bot-token mode can only send messages."
        )
        raise TelegramClientError(msg)

    def _resolve_target(self, channel_id: str) -> object:
        """Resolve a public channel ID into a Telethon entity when possible."""
        return run_coroutine(self._resolve_target_async(channel_id))

    async def _resolve_target_async(self, channel_id: str) -> object:
        """Resolve a listed channel/chat/user ID for Telethon calls.

        Telethon cannot always resolve a private user/chat from a bare integer ID.
        Dialog entities carry the access hash and peer details Telethon needs, so
        refresh dialogs and reuse the matching entity when possible.
        """
        if self._bot_mode:
            return _coerce_channel_id(channel_id)

        cached = self._entity_cache.get(channel_id)
        if cached is not None:
            return cached

        dialogs = await self._get_client().get_dialogs()
        for dialog in dialogs:
            self._cache_dialog_entity(dialog)

        cached = self._entity_cache.get(channel_id)
        if cached is not None:
            return cached

        return _coerce_channel_id(channel_id)

    def _cache_dialog_entity(self, dialog: object) -> None:
        entity = getattr(dialog, "entity", dialog)
        entity_id = getattr(entity, "id", None)
        if entity_id is not None:
            self._entity_cache[str(entity_id)] = entity


def get_client_impl() -> ChatClient:
    """Return a ``ChatClient`` instance (used by ``register_client`` and tests)."""
    config = TelegramClientConfig.from_env()
    return TelegramClient(config=config)


def _require_non_empty(*, value: str, name: str) -> None:
    """Validate required string parameters."""
    if not value:
        msg = f"{name} must be non-empty"
        raise ValueError(msg)


def _coerce_channel_id(channel_id: str) -> int | str:
    try:
        return int(channel_id)
    except ValueError:
        return channel_id
