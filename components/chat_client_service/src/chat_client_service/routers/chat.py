"""Chat operation endpoints delegating through chat_client_api."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

import telegram_client_impl  # noqa: F401
from chat_client_api import ChatClient, get_client
from chat_client_service.models import (
    ChannelModel,
    DeleteMessageResponse,
    MessageModel,
    SendMessageRequest,
)
from chat_client_service.routers.auth import get_current_token

router = APIRouter(
    prefix="/chat",
    tags=["chat"],
    dependencies=[Depends(get_current_token)],
)


def get_chat_client() -> ChatClient:
    """FastAPI dependency that returns a Telegram-backed ChatClient.

    Override via ``app.dependency_overrides[get_chat_client]`` in tests.
    """
    return get_client()


@router.post("/messages")
def send_message(
    payload: SendMessageRequest,
    client: Annotated[ChatClient, Depends(get_chat_client)],
) -> MessageModel:
    """Send a message to a channel via telegram_client_impl."""
    try:
        msg = client.send_message(channel_id=payload.channel_id, text=payload.text)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc
    return MessageModel(
        id=msg.message_id,
        sender=msg.sender,
        channel_id=msg.channel,
        timestamp=msg.timestamp,
        text=msg.text,
    )


@router.get("/messages")
def get_messages(
    client: Annotated[ChatClient, Depends(get_chat_client)],
    channel_id: Annotated[str, Query(min_length=1)],
    limit: Annotated[int | None, Query(gt=0)] = None,
    max_results: Annotated[int | None, Query(gt=0)] = None,
) -> list[MessageModel]:
    """Retrieve messages from a channel via telegram_client_impl."""
    effective_limit = limit if limit is not None else max_results or 10
    try:
        msgs = client.get_messages(channel_id=channel_id, limit=effective_limit)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc
    return [
        MessageModel(
            id=m.message_id,
            sender=m.sender,
            channel_id=m.channel,
            timestamp=m.timestamp,
            text=m.text,
        )
        for m in msgs
    ]


@router.get("/messages/{message_id}")
def get_message(
    client: Annotated[ChatClient, Depends(get_chat_client)],
    message_id: str,
) -> MessageModel:
    """Retrieve a single message by opaque id."""
    try:
        msg = client.get_message(message_id=message_id)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc
    return MessageModel(
        id=msg.message_id,
        sender=msg.sender,
        channel_id=msg.channel,
        timestamp=msg.timestamp,
        text=msg.text,
    )


@router.delete("/messages/{message_id}")
def delete_message(
    client: Annotated[ChatClient, Depends(get_chat_client)],
    message_id: str,
) -> DeleteMessageResponse:
    """Delete a message via telegram_client_impl."""
    try:
        client.delete_message(message_id=message_id)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc
    return DeleteMessageResponse(success=True)


@router.get("/channels")
def get_channels(
    client: Annotated[ChatClient, Depends(get_chat_client)],
) -> list[ChannelModel]:
    """List available channels via telegram_client_impl."""
    try:
        channels = list(client.get_channels())
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc
    return [
        ChannelModel(
            id=ch.channel_id,
            name=ch.name,
            channel_type=ch.channel_type,
        )
        for ch in channels
    ]
