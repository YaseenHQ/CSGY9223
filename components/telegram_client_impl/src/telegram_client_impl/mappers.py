"""Mapping helpers from Telegram provider objects to API contract objects."""

from telegram_client_impl.channel import TelegramChannel
from telegram_client_impl.message import TelegramMessage


def to_channel(raw_channel: object | None) -> TelegramChannel:
    """Convert a raw Telegram channel/chat object to TelegramChannel."""
    if raw_channel is None:
        msg = "raw_channel cannot be None"
        raise ValueError(msg)
    raise NotImplementedError


def to_message(raw_message: object | None) -> TelegramMessage:
    """Convert a raw Telegram message object to TelegramMessage."""
    if raw_message is None:
        msg = "raw_message cannot be None"
        raise ValueError(msg)
    raise NotImplementedError
