"""Shared API models for the chat client service scaffold."""

from pydantic import BaseModel, Field


class ChannelModel(BaseModel):
    """Transport model for a channel."""

    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    channel_type: str = Field(min_length=1)


class MessageModel(BaseModel):
    """Transport model for a message."""

    id: str = Field(min_length=1)
    sender: str
    channel_id: str = Field(min_length=1)
    timestamp: str
    text: str


class SendMessageRequest(BaseModel):
    """Request payload for sending a message."""

    channel_id: str = Field(min_length=1)
    text: str = Field(min_length=1)


class DeleteMessageResponse(BaseModel):
    """Response payload for delete message operations."""

    success: bool


class OAuthLoginResponse(BaseModel):
    """Response payload for OAuth login initiation placeholder."""

    authorization_url: str
    state: str


class OAuthCallbackResponse(BaseModel):
    """Response payload for OAuth callback placeholder."""

    detail: str
    code: str | None = None
    state: str | None = None
