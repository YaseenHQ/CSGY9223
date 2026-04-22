"""Telegram OIDC authentication routes."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import RedirectResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from chat_client_service.models import (
    MeResponse,
    TelegramLoginCallbackRequest,
    TelegramLoginConfigResponse,
    TokenResponse,
)
from chat_client_service.oidc import (
    OidcConfig,
    begin_login,
    begin_login_library,
    complete_login,
    complete_login_library,
    decode_app_token,
)
from telegram_client_impl.store import StoredChannel, get_store

router = APIRouter(prefix="/auth", tags=["auth"])
_bearer = HTTPBearer(auto_error=False)


def get_oidc_config() -> OidcConfig:
    """Return OIDC config from environment."""
    return OidcConfig.from_env()


def get_current_claims(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(_bearer),
    ],
    config: Annotated[OidcConfig, Depends(get_oidc_config)],
) -> dict[str, str]:
    """Return validated local session claims or raise 401."""
    if credentials is None:
        raise _unauthorized()
    claims = decode_app_token(config=config, token=credentials.credentials)
    if claims is None:
        raise _unauthorized()
    return claims


@router.get("/login")
def auth_login(
    config: Annotated[OidcConfig, Depends(get_oidc_config)],
) -> RedirectResponse:
    """Start Telegram OIDC Authorization Code Flow with PKCE."""
    try:
        url, _state = begin_login(config)
    except (TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc
    return RedirectResponse(url=url, status_code=status.HTTP_302_FOUND)


@router.get("/login/config")
def auth_login_config(
    config: Annotated[OidcConfig, Depends(get_oidc_config)],
) -> TelegramLoginConfigResponse:
    """Return init data for Telegram.Login JavaScript library."""
    try:
        client_id, nonce = begin_login_library(config)
    except (TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc
    return TelegramLoginConfigResponse(client_id=client_id, nonce=nonce)


@router.get("/callback")
def auth_callback(
    code: str,
    state: str,
    config: Annotated[OidcConfig, Depends(get_oidc_config)],
) -> TokenResponse:
    """Complete Telegram OIDC login and issue a local Bearer token."""
    try:
        token = complete_login(config=config, code=code, state=state)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    return _issue_token_response(config=config, token=token)


@router.post("/callback")
def auth_login_library_callback(
    request: TelegramLoginCallbackRequest,
    config: Annotated[OidcConfig, Depends(get_oidc_config)],
) -> TokenResponse:
    """Complete Telegram.Login JavaScript id_token callback."""
    try:
        token = complete_login_library(
            config=config,
            id_token=request.id_token,
            nonce=request.nonce,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    return _issue_token_response(config=config, token=token)


ClaimsDependency = Annotated[dict[str, str], Depends(get_current_claims)]


@router.get("/me")
def auth_me(claims: ClaimsDependency) -> MeResponse:
    """Return identity from the authenticated local session."""
    return MeResponse(
        telegram_id=claims.get("telegram_id", ""),
        username=claims.get("username"),
        name=claims.get("name"),
    )


def _unauthorized() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated. Start at /auth/login.",
        headers={"WWW-Authenticate": "Bearer"},
    )


def _issue_token_response(*, config: OidcConfig, token: str) -> TokenResponse:
    claims = decode_app_token(config=config, token=token)
    if claims is not None:
        _grant_self_chat_access(claims)
    return TokenResponse(access_token=token)


def _grant_self_chat_access(claims: dict[str, str]) -> None:
    telegram_id = claims.get("telegram_id", "")
    if not telegram_id:
        return
    name = claims.get("username") or claims.get("name") or telegram_id
    store = get_store()
    store.upsert_channel(
        StoredChannel(
            channel_id=telegram_id,
            name=name,
            channel_type="private",
        )
    )
    store.grant_access(telegram_id=telegram_id, channel_id=telegram_id)
