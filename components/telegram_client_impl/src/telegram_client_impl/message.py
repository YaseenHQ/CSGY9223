"""Telegram Message scaffold model implementing the Message contract."""

from chat_client_api.message import Message


class TelegramMessage(Message):
    """Concrete message model for Telegram-backed messages."""

    def __init__(
        self,
        *,
        message_id: str,
        sender: str,
        channel_id: str,
        timestamp: str,
        text: str,
    ) -> None:
        """Initialize a Telegram message scaffold model."""
        self._id = message_id
        self._sender = sender
        self._channel_id = channel_id
        self._timestamp = timestamp
        self._text = text

    @property
    def id(self) -> str:
        """Return the unique identifier of the message."""
        return self._id

    @property
    def sender(self) -> str:
        """Return the sender identifier."""
        return self._sender

    @property
    def channel_id(self) -> str:
        """Return the channel identifier."""
        return self._channel_id

    @property
    def timestamp(self) -> str:
        """Return an ISO timestamp for when the message was sent."""
        return self._timestamp

    @property
    def text(self) -> str:
        """Return the message body."""
        return self._text


def get_message_impl(msg_id: str, raw_data: str) -> Message:
    """Build a message instance from raw provider data.

    This is a scaffold placeholder and intentionally unimplemented.
    """
    if not msg_id:
        msg = "msg_id must be non-empty"
        raise ValueError(msg)
    if not raw_data:
        msg = "raw_data must be non-empty"
        raise ValueError(msg)
    raise NotImplementedError
