"""Mapping helpers from Telegram Bot API objects to API contract objects."""

from datetime import datetime, timezone

from telegram_client_impl.channel import TelegramChannel
from telegram_client_impl.errors import TelegramMappingError
from telegram_client_impl.message import TelegramMessage


def to_channel(raw_channel: object | None) -> TelegramChannel:
    """Convert a Bot API chat object to TelegramChannel."""
    if raw_channel is None:
        msg = "raw_channel cannot be None"
        raise ValueError(msg)

    if not isinstance(raw_channel, dict):
        msg = f"Unsupported channel entity type: {type(raw_channel)!r}"
        raise TelegramMappingError(msg)

    channel_id = str(raw_channel.get("id", ""))
    title = (
        raw_channel.get("title")
        or raw_channel.get("username")
        or raw_channel.get("first_name")
        or channel_id
    )
    return TelegramChannel(
        channel_id=channel_id,
        name=str(title),
        channel_type=str(raw_channel.get("type") or "unknown"),
    )


def to_message(raw_message: object | None) -> TelegramMessage:
    """Convert a Bot API message object to TelegramMessage."""
    if raw_message is None:
        msg = "raw_message cannot be None"
        raise ValueError(msg)

    if not isinstance(raw_message, dict):
        msg = f"Unsupported message type: {type(raw_message)!r}"
        raise TelegramMappingError(msg)

    chat = raw_message.get("chat")
    sender = raw_message.get("from")
    chat_obj = chat if isinstance(chat, dict) else {}
    sender_obj = sender if isinstance(sender, dict) else {}
    timestamp_raw = raw_message.get("date")
    timestamp = (
        datetime.fromtimestamp(timestamp_raw, tz=timezone.utc).isoformat()
        if isinstance(timestamp_raw, int)
        else str(timestamp_raw or "")
    )
    return TelegramMessage(
        message_id=str(raw_message.get("message_id", "")),
        sender=str(sender_obj.get("id", "")),
        channel_id=str(chat_obj.get("id", "")),
        timestamp=timestamp,
        text=str(raw_message.get("text") or raw_message.get("caption") or ""),
    )
