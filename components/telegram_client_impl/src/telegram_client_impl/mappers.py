"""Mapping helpers from Telegram provider objects to shared API dataclasses."""

from telethon.tl.custom.dialog import Dialog as _Dialog
from telethon.tl.custom.message import Message as _CustomMessage
from telethon.tl.types import (
    Channel as _Channel,
)
from telethon.tl.types import (
    Chat as _Chat,
)
from telethon.tl.types import (
    PeerChannel,
    PeerChat,
    PeerUser,
)
from telethon.tl.types import (
    User as _User,
)

from chat_client_api import Channel, Message
from telegram_client_impl.errors import TelegramMappingError
from telegram_client_impl.opaque_ids import encode_telegram_message_id


def to_channel(raw_channel: object | None) -> Channel:
    """Convert a raw Telegram channel/chat object to shared ``Channel``."""
    if raw_channel is None:
        msg = "raw_channel cannot be None"
        raise ValueError(msg)

    entity: object = (
        raw_channel.entity if isinstance(raw_channel, _Dialog) else raw_channel
    )

    if isinstance(entity, (_Channel, _Chat, _User)):  # pragma: no cover
        channel_id = str(entity.id)

        name: str
        if getattr(entity, "title", None):
            name = str(entity.title)
        elif getattr(entity, "first_name", None):
            name = str(entity.first_name)
        elif getattr(entity, "username", None):
            name = str(entity.username)
        else:
            name = channel_id

        if isinstance(entity, _User):
            channel_type = "private"
            is_private = True
        elif isinstance(entity, _Channel):
            channel_type = "channel" if getattr(entity, "broadcast", False) else "group"
            is_private = False
        else:
            channel_type = "group"
            is_private = False

        return Channel(
            channel_id=channel_id,
            name=name,
            is_private=is_private,
            channel_type=channel_type,
        )

    # Duck-typed fallback for Telethon-like objects (e.g. test doubles).
    eid = getattr(entity, "id", None)
    if eid is not None:
        cid = str(eid)
        name = (
            str(getattr(entity, "title", None) or "")
            or str(getattr(entity, "first_name", None) or "")
            or str(getattr(entity, "username", None) or "")
            or cid
        )
        is_private = bool(getattr(entity, "first_name", None)) and not getattr(
            entity, "title", None
        )
        channel_type = "channel" if getattr(entity, "broadcast", False) else "group"
        return Channel(
            channel_id=cid,
            name=name or cid,
            is_private=is_private,
            channel_type=channel_type,
        )

    msg = f"Unsupported channel entity type: {type(raw_channel)!r}"
    raise TelegramMappingError(msg)


def _channel_id_from_duck_peer(peer: object) -> str:
    """Resolve chat id from a Telethon-like ``peer_id`` object (test doubles)."""
    if getattr(peer, "channel_id", None) is not None:
        return str(getattr(peer, "channel_id", None))
    if getattr(peer, "chat_id", None) is not None:
        return str(getattr(peer, "chat_id", None))
    if getattr(peer, "user_id", None) is not None:
        return str(getattr(peer, "user_id", None))
    return ""


def _require_non_empty_chat_id_for_message(channel_id: str) -> None:
    if not channel_id:
        msg = "Cannot map message: peer has no channel_id, chat_id, or user_id"
        raise TelegramMappingError(msg)


def to_message(raw_message: object | None) -> Message:
    """Convert a raw Telegram message object to shared ``Message`` with opaque id."""
    if raw_message is None:
        msg = "raw_message cannot be None"
        raise ValueError(msg)

    if not isinstance(raw_message, _CustomMessage):
        # Duck-typed fallback for Telethon-like objects (e.g. test doubles).
        if (
            getattr(raw_message, "id", None) is not None
            and getattr(raw_message, "peer_id", None) is not None
        ):
            msg_obj = raw_message
            inner_id = getattr(msg_obj, "id", None)
            sender = (
                str(getattr(msg_obj, "sender_id", None))
                if getattr(msg_obj, "sender_id", None) is not None
                else ""
            )
            peer = getattr(msg_obj, "peer_id", None)
            ch_id = _channel_id_from_duck_peer(peer)
            _require_non_empty_chat_id_for_message(ch_id)
            date_val = getattr(msg_obj, "date", None)
            timestamp = date_val.isoformat() if date_val is not None else ""
            text = getattr(msg_obj, "message", None) or ""
            opaque = encode_telegram_message_id(
                chat_id=ch_id,
                telegram_message_id=int(inner_id) if inner_id is not None else 0,
            )
            return Message(
                message_id=opaque,
                channel=ch_id,
                text=text,
                sender=sender,
                timestamp=timestamp,
            )
        msg = f"Unsupported message type: {type(raw_message)!r}"
        raise TelegramMappingError(msg)

    msg_obj = raw_message  # pragma: no cover - Telethon Message type

    inner_id = msg_obj.id  # pragma: no cover
    sender = (
        str(msg_obj.sender_id) if msg_obj.sender_id is not None else ""
    )  # pragma: no cover

    channel_id: str  # pragma: no cover
    peer = msg_obj.peer_id  # pragma: no cover
    if isinstance(peer, PeerChannel):  # pragma: no cover
        channel_id = str(peer.channel_id)
    elif isinstance(peer, PeerChat):
        channel_id = str(peer.chat_id)
    elif isinstance(peer, PeerUser):
        channel_id = str(peer.user_id)
    else:
        channel_id = ""

    _require_non_empty_chat_id_for_message(channel_id)

    timestamp = (
        msg_obj.date.isoformat() if msg_obj.date is not None else ""
    )  # pragma: no cover
    text = msg_obj.message or ""  # pragma: no cover

    opaque = encode_telegram_message_id(
        chat_id=channel_id,
        telegram_message_id=inner_id,
    )

    return Message(  # pragma: no cover
        message_id=opaque,
        channel=channel_id,
        text=text,
        sender=sender,
        timestamp=timestamp,
    )
