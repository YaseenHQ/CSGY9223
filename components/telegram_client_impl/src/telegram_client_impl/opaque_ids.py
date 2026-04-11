"""Opaque Telegram message identifiers: ``<chat_id>:<telegram_message_id>``.

Parse with ``split(":", 1)`` so numeric IDs stay unambiguous.
"""

from __future__ import annotations


def encode_telegram_message_id(*, chat_id: str, telegram_message_id: str | int) -> str:
    """Build opaque ``message_id`` for shared API ``Message`` objects.

    Raises:
        ValueError: If ``chat_id`` is empty (must match ``parse_telegram_message_id``).

    """
    if not chat_id:
        msg = "chat_id must be non-empty for opaque message_id encoding"
        raise ValueError(msg)
    return f"{chat_id}:{int(telegram_message_id)}"


def parse_telegram_message_id(message_id: str) -> tuple[int, int]:
    """Split an opaque id into Telethon peer id and message id.

    Raises:
        ValueError: If the string is empty, has no separator, or parts are not integers.

    """
    if not message_id:
        msg = "message_id must be non-empty"
        raise ValueError(msg)
    if ":" not in message_id:
        msg = (
            "Invalid message_id format; expected '<chat_id>:<telegram_message_id>' "
            "(use split(':', 1) when decoding)"
        )
        raise ValueError(msg)
    chat_part, msg_part = message_id.split(":", 1)
    if not chat_part or not msg_part:
        msg = "Invalid message_id: empty chat_id or telegram_message_id segment"
        raise ValueError(msg)
    try:
        return int(chat_part), int(msg_part)
    except ValueError as exc:
        msg = "Invalid message_id: chat_id and telegram_message_id must be integers"
        raise ValueError(msg) from exc
