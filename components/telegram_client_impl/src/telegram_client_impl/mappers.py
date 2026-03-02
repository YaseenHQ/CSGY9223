"""Mapping helpers from Telegram provider objects to API contract objects."""

from telethon.tl.custom.dialog import Dialog as _Dialog
from telethon.tl.custom.message import Message as _CustomMessage
from telethon.tl.types import Channel as _Channel
from telethon.tl.types import Chat as _Chat
from telethon.tl.types import PeerChannel, PeerChat, PeerUser
from telethon.tl.types import User as _User

from telegram_client_impl.channel import TelegramChannel
from telegram_client_impl.errors import TelegramMappingError
from telegram_client_impl.message import TelegramMessage


def to_channel(raw_channel: object | None) -> TelegramChannel:
    """Convert a raw Telegram channel/chat object to TelegramChannel."""
    if raw_channel is None:
        msg = "raw_channel cannot be None"
        raise ValueError(msg)

    entity: object = (
        raw_channel.entity if isinstance(raw_channel, _Dialog) else raw_channel
    )

    if isinstance(entity, (_Channel, _Chat, _User)):
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
        elif isinstance(entity, _Channel):
            channel_type = (
                "channel" if getattr(entity, "broadcast", False) else "group"
            )
        else:
            channel_type = "group"

        return TelegramChannel(
            channel_id=channel_id, name=name, channel_type=channel_type
        )

    msg = f"Unsupported channel entity type: {type(raw_channel)!r}"
    raise TelegramMappingError(msg)


def to_message(raw_message: object | None) -> TelegramMessage:
    """Convert a raw Telegram message object to TelegramMessage."""
    if raw_message is None:
        msg = "raw_message cannot be None"
        raise ValueError(msg)

    if not isinstance(raw_message, _CustomMessage):
        msg = f"Unsupported message type: {type(raw_message)!r}"
        raise TelegramMappingError(msg)

    msg_obj = raw_message

    message_id = str(msg_obj.id)
    sender = str(msg_obj.sender_id) if msg_obj.sender_id is not None else ""

    channel_id: str
    peer = msg_obj.peer_id
    if isinstance(peer, PeerChannel):
        channel_id = str(peer.channel_id)
    elif isinstance(peer, PeerChat):
        channel_id = str(peer.chat_id)
    elif isinstance(peer, PeerUser):
        channel_id = str(peer.user_id)
    else:
        channel_id = ""

    timestamp = msg_obj.date.isoformat() if msg_obj.date is not None else ""
    text = msg_obj.message or ""

    return TelegramMessage(
        message_id=message_id,
        sender=sender,
        channel_id=channel_id,
        timestamp=timestamp,
        text=text,
    )

