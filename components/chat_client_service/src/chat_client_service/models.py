"""Transport models for the chat client service."""

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """Health endpoint response."""

    status: str


class ChannelModel(BaseModel):
    """HTTP model for a Telegram chat known to the bot."""

    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    channel_type: str = Field(min_length=1)


class MessageModel(BaseModel):
    """HTTP model for a Telegram message."""

    id: str = Field(min_length=1)
    sender: str
    channel_id: str = Field(min_length=1)
    timestamp: str
    text: str


class SendMessageRequest(BaseModel):
    """Request body for sending a message."""

    channel_id: str = Field(min_length=1)
    text: str = Field(min_length=1, max_length=4096)


class DeleteMessageResponse(BaseModel):
    """Response body for deleting a message."""

    success: bool


class AuthSessionResponse(BaseModel):
    """Pending service auth session response."""

    session_id: str
    authenticated: bool
    login_url: str
    status_url: str


class AuthSessionStatusResponse(BaseModel):
    """Current service auth session state."""

    session_id: str
    authenticated: bool
    telegram_id: str | None = None
    username: str | None = None
    name: str | None = None


class LogoutResponse(BaseModel):
    """Service auth session deletion response."""

    success: bool


class TokenResponse(BaseModel):
    """Bearer token issued by this service after Telegram OIDC login."""

    access_token: str
    token_type: str = "bearer"  # noqa: S105


class TelegramLoginConfigResponse(BaseModel):
    """Configuration for the Telegram Login JavaScript library."""

    client_id: str
    nonce: str
    origin: str


class TelegramLoginCallbackRequest(BaseModel):
    """ID token callback payload from Telegram.Login JavaScript."""

    id_token: str = Field(min_length=1)
    nonce: str = Field(min_length=1)


class MeResponse(BaseModel):
    """Authenticated Telegram identity extracted from the service token."""

    telegram_id: str
    username: str | None = None
    name: str | None = None
