"""Telegram Channel model implementing the Channel contract."""

from chat_client_api import Channel


class TelegramChannel(Channel):
    """Concrete channel model for Telegram-backed channels/chats."""

    def __init__(self, *, channel_id: str, name: str, channel_type: str) -> None:
        """Initialize a Telegram channel model."""
        self._id = channel_id
        self._name = name
        self._channel_type = channel_type

    @property
    def id(self) -> str:
        """Return the unique identifier of the channel."""
        return self._id

    @property
    def channel_id(self) -> str:
        """Return the shared API channel identifier."""
        return self._id

    @property
    def name(self) -> str:
        """Return the display name of the channel."""
        return self._name

    @property
    def channel_type(self) -> str:
        """Return the type of channel (e.g. group/private/channel)."""
        return self._channel_type

    @property
    def is_private(self) -> bool | None:
        """Return whether Telegram marks this as a private chat."""
        if self._channel_type == "private":
            return True
        if self._channel_type in {"group", "supergroup", "channel"}:
            return False
        return None
