"""OAuth-related scaffold endpoints."""

from typing import Annotated

from fastapi import APIRouter, Query

from chat_client_service.models import OAuthCallbackResponse, OAuthLoginResponse

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/login")
def auth_login() -> OAuthLoginResponse:
    """Return placeholder auth-init metadata for future OAuth redirect flow."""
    return OAuthLoginResponse(
        authorization_url="https://oauth.telegram.org/auth",
        state="scaffold-state",
    )


@router.get("/callback")
def auth_callback(
    code: Annotated[str | None, Query()] = None,
    state: Annotated[str | None, Query()] = None,
) -> OAuthCallbackResponse:
    """Return placeholder callback handling response."""
    return OAuthCallbackResponse(
        detail="OAuth callback scaffold endpoint.",
        code=code,
        state=state,
    )
