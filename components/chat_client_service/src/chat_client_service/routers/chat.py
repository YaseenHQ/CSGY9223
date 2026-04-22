"""Protected chat routes backed by the Telegram Bot API client."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

import telegram_client_impl  # noqa: F401  # factory injection side effect
from chat_client_api import Channel, Client, Message, get_client
from chat_client_service.models import (
    ChannelModel,
    DeleteMessageResponse,
    MessageModel,
    SendMessageRequest,
)
from chat_client_service.routers.auth import get_current_claims
from telegram_client_impl.errors import TelegramClientError
from telegram_client_impl.store import get_store

router = APIRouter(
    prefix="/chat",
    tags=["chat"],
    dependencies=[Depends(get_current_claims)],
)


def get_chat_client() -> Client:
    """Return the configured chat client implementation."""
    return get_client(interactive=False)


@router.post("/messages")
def send_message(
    request: SendMessageRequest,
    claims: Annotated[dict[str, str], Depends(get_current_claims)],
    client: Annotated[Client, Depends(get_chat_client)],
) -> MessageModel:
    """Send a message to a known Telegram chat through the service bot."""
    channel_id = _resolve_channel_id(claims=claims, channel_id=request.channel_id)
    _require_channel_access(claims=claims, channel_id=channel_id, client=client)
    try:
        message = client.send_message(channel_id, request.text)
        get_store().grant_access(
            telegram_id=claims.get("telegram_id", ""),
            channel_id=channel_id,
        )
        return _message_model(message)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc


@router.get("/messages")
def get_messages(
    channel_id: str,
    claims: Annotated[dict[str, str], Depends(get_current_claims)],
    client: Annotated[Client, Depends(get_chat_client)],
    limit: Annotated[int | None, Query(gt=0)] = None,
    max_results: Annotated[int | None, Query(gt=0)] = None,
) -> list[MessageModel]:
    """Return bot-observed messages for a known Telegram chat."""
    channel_id = _resolve_channel_id(claims=claims, channel_id=channel_id)
    _require_channel_access(claims=claims, channel_id=channel_id, client=client)
    requested_limit = limit if limit is not None else (max_results or 10)
    try:
        return [
            _message_model(message)
            for message in client.get_messages(
                channel_id=channel_id,
                limit=requested_limit,
            )
        ]
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc


@router.get("/messages/{message_id}")
def get_message(
    message_id: str,
    claims: Annotated[dict[str, str], Depends(get_current_claims)],
    client: Annotated[Client, Depends(get_chat_client)],
) -> MessageModel:
    """Return one bot-observed message by its opaque ID."""
    try:
        message = client.get_message(message_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc
    _require_channel_access(claims=claims, channel_id=message.channel_id, client=client)
    return _message_model(message)


@router.delete("/messages/{message_id}")
def delete_message(
    message_id: str,
    claims: Annotated[dict[str, str], Depends(get_current_claims)],
    client: Annotated[Client, Depends(get_chat_client)],
    channel_id: str | None = None,
) -> DeleteMessageResponse:
    """Delete a message if the service bot has Telegram permission."""
    channel_id, provider_message_id = _resolve_delete_reference(
        claims=claims,
        message_id=message_id,
        channel_id=channel_id,
    )
    _require_channel_access(claims=claims, channel_id=channel_id, client=client)
    try:
        client.delete_message(message_id=f"{channel_id}:{provider_message_id}")
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc
    return DeleteMessageResponse(success=True)


@router.get("/channels")
def get_channels(
    claims: Annotated[dict[str, str], Depends(get_current_claims)],
    client: Annotated[Client, Depends(get_chat_client)],
) -> list[ChannelModel]:
    """Return chats known to the service bot."""
    try:
        return [
            _channel_model(channel)
            for channel in client.get_channels()
            if _can_access_channel(claims=claims, channel_id=channel.id, client=client)
        ]
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc


@router.get("/channels/{channel_id}")
def get_channel(
    channel_id: str,
    claims: Annotated[dict[str, str], Depends(get_current_claims)],
    client: Annotated[Client, Depends(get_chat_client)],
) -> ChannelModel:
    """Return one chat known to the service bot."""
    channel_id = _resolve_channel_id(claims=claims, channel_id=channel_id)
    _require_channel_access(claims=claims, channel_id=channel_id, client=client)
    try:
        return _channel_model(client.get_channel(channel_id))
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc


def _message_model(message: Message) -> MessageModel:
    return MessageModel(
        id=_opaque_message_id(message),
        sender=message.sender,
        channel_id=message.channel_id,
        timestamp=message.timestamp,
        text=message.text,
    )


def _channel_model(channel: Channel) -> ChannelModel:
    return ChannelModel(
        id=channel.id,
        name=channel.name,
        channel_type=channel.channel_type,
    )


def _require_channel_access(
    *,
    claims: dict[str, str],
    channel_id: str,
    client: Client,
) -> None:
    if not _can_access_channel(claims=claims, channel_id=channel_id, client=client):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized for this Telegram chat",
        )


def _can_access_channel(
    *,
    claims: dict[str, str],
    channel_id: str,
    client: Client,
) -> bool:
    telegram_id = claims.get("telegram_id", "")
    store = get_store()
    if store.user_can_access(telegram_id=telegram_id, channel_id=channel_id):
        return True

    checker = getattr(type(client), "user_can_access_channel", None)
    if not callable(checker):
        return False
    try:
        allowed = bool(
            checker(
                client,
                user_id=telegram_id,
                channel_id=channel_id,
            )
        )
    except (TelegramClientError, ValueError):
        return False
    if allowed:
        store.grant_access(telegram_id=telegram_id, channel_id=channel_id)
    return allowed


def _resolve_channel_id(*, claims: dict[str, str], channel_id: str) -> str:
    if channel_id == "me":
        return claims.get("telegram_id", "")
    return channel_id


def _resolve_delete_reference(
    *,
    claims: dict[str, str],
    message_id: str,
    channel_id: str | None,
) -> tuple[str, str]:
    if channel_id is not None:
        resolved_channel_id = _resolve_channel_id(claims=claims, channel_id=channel_id)
        if ":" in message_id:
            embedded_channel_id, provider_message_id = message_id.split(":", 1)
            embedded_channel_id = _resolve_channel_id(
                claims=claims,
                channel_id=embedded_channel_id,
            )
            if embedded_channel_id != resolved_channel_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="message_id channel does not match channel_id",
                )
            return resolved_channel_id, provider_message_id
        return resolved_channel_id, message_id
    if ":" in message_id:
        resolved_channel_id, provider_message_id = message_id.split(":", 1)
        return (
            _resolve_channel_id(claims=claims, channel_id=resolved_channel_id),
            provider_message_id,
        )

    stored = get_store().get_message(message_id=message_id)
    if stored is not None:
        return stored.channel_id, stored.id
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Use the returned opaque message id or include channel_id",
    )


def _opaque_message_id(message: Message) -> str:
    return f"{message.channel_id}:{message.id}"
