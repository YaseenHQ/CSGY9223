"""Chat operation scaffold endpoints."""

from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status

from chat_client_service.models import (
    ChannelModel,
    DeleteMessageResponse,
    MessageModel,
    SendMessageRequest,
)

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("/messages")
def send_message(payload: SendMessageRequest) -> MessageModel:
    """Send-message endpoint scaffold."""
    _ = payload
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="send_message is not implemented in scaffold.",
    )


@router.get("/messages")
def get_messages(
    channel_id: Annotated[str, Query(min_length=1)],
    max_results: Annotated[int, Query(gt=0)] = 10,
) -> list[MessageModel]:
    """Get-messages endpoint scaffold."""
    _ = (channel_id, max_results)
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="get_messages is not implemented in scaffold.",
    )


@router.delete("/messages/{message_id}")
def delete_message(
    message_id: str,
    channel_id: Annotated[str, Query(min_length=1)],
) -> DeleteMessageResponse:
    """Delete-message endpoint scaffold."""
    _ = (message_id, channel_id)
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="delete_message is not implemented in scaffold.",
    )


@router.get("/channels")
def get_channels() -> list[ChannelModel]:
    """Get-channels endpoint scaffold."""
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="get_channels is not implemented in scaffold.",
    )
