"""Telegram OIDC authentication routes."""

import json
import secrets
import time
from typing import Annotated
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from chat_client_service.models import (
    AuthSessionResponse,
    AuthSessionStatusResponse,
    LogoutResponse,
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
    x_session_id: Annotated[str | None, Header(alias="X-Session-ID")] = None,
) -> dict[str, str]:
    """Return validated local session claims or raise 401."""
    token: str | None = None
    if credentials is None:
        if x_session_id is not None:
            token = get_store().token_for_session(session_id=x_session_id)
    else:
        token = credentials.credentials
    if token is None:
        raise _unauthorized()

    claims = decode_app_token(config=config, token=token)
    if claims is None:
        raise _unauthorized()
    return claims


@router.post(
    "/sessions",
    status_code=status.HTTP_201_CREATED,
)
def create_auth_session(
    config: Annotated[OidcConfig, Depends(get_oidc_config)],
) -> AuthSessionResponse:
    """Create a pending service auth session for adapter clients."""
    session_id = secrets.token_urlsafe(24)
    get_store().create_auth_session(
        session_id=session_id,
        created_at=int(time.time()),
    )
    return AuthSessionResponse(
        session_id=session_id,
        authenticated=False,
        login_url=_session_login_url(config=config, session_id=session_id),
        status_url=_session_status_url(config=config, session_id=session_id),
    )


@router.get("/login", response_model=None)
def auth_login(
    config: Annotated[OidcConfig, Depends(get_oidc_config)],
    session_id: Annotated[str | None, Query(min_length=1)] = None,
    flow: Annotated[str, Query(pattern="^(page|code)$")] = "page",
) -> HTMLResponse | RedirectResponse:
    """Start Telegram Login with OIDC code flow or the hosted page fallback."""
    _require_known_session(session_id)
    if flow == "code":
        return _auth_code_redirect(config=config, session_id=session_id)

    try:
        client_id, nonce = begin_login_library(config, session_id=session_id)
    except (TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc
    return HTMLResponse(
        content=_login_page_html(
            client_id=client_id,
            nonce=nonce,
            origin=config.service_base_url.rstrip("/"),
            session_id=session_id,
        )
    )


def _auth_code_redirect(
    *,
    config: OidcConfig,
    session_id: str | None,
) -> RedirectResponse:
    try:
        url, _state = begin_login(config, session_id=session_id)
    except (TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc
    return RedirectResponse(url=url, status_code=status.HTTP_302_FOUND)


@router.get("/login/config")
def auth_login_config(
    config: Annotated[OidcConfig, Depends(get_oidc_config)],
    session_id: Annotated[str | None, Query(min_length=1)] = None,
) -> TelegramLoginConfigResponse:
    """Return init data for Telegram.Login JavaScript library."""
    _require_known_session(session_id)
    try:
        client_id, nonce = begin_login_library(config, session_id=session_id)
    except (TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc
    return TelegramLoginConfigResponse(
        client_id=client_id,
        nonce=nonce,
        origin=config.service_base_url.rstrip("/"),
    )


@router.get("/callback")
def auth_callback(
    code: str,
    state: str,
    config: Annotated[OidcConfig, Depends(get_oidc_config)],
) -> TokenResponse:
    """Complete Telegram OIDC login and issue a local Bearer token."""
    try:
        token, session_id = complete_login(config=config, code=code, state=state)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    return _issue_token_response(config=config, token=token, session_id=session_id)


@router.post("/callback")
def auth_login_library_callback(
    request: TelegramLoginCallbackRequest,
    config: Annotated[OidcConfig, Depends(get_oidc_config)],
) -> TokenResponse:
    """Complete Telegram.Login JavaScript id_token callback."""
    try:
        token, session_id = complete_login_library(
            config=config,
            id_token=request.id_token,
            nonce=request.nonce,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    return _issue_token_response(config=config, token=token, session_id=session_id)


ClaimsDependency = Annotated[dict[str, str], Depends(get_current_claims)]


@router.get("/me")
def auth_me(claims: ClaimsDependency) -> MeResponse:
    """Return identity from the authenticated local session."""
    return MeResponse(
        telegram_id=claims.get("telegram_id", ""),
        username=claims.get("username"),
        name=claims.get("name"),
    )


@router.get("/sessions/{session_id}")
def get_auth_session(
    session_id: str,
    config: Annotated[OidcConfig, Depends(get_oidc_config)],
) -> AuthSessionStatusResponse:
    """Return the current auth state for a service session."""
    session = get_store().get_auth_session(session_id=session_id)
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Unknown auth session.",
        )
    authenticated = (
        session.token is not None
        and decode_app_token(config=config, token=session.token) is not None
    )
    return AuthSessionStatusResponse(
        session_id=session.session_id,
        authenticated=authenticated,
        telegram_id=session.telegram_id,
        username=session.username,
        name=session.name,
    )


@router.delete("/sessions/{session_id}")
def delete_auth_session(session_id: str) -> LogoutResponse:
    """Delete a service auth session."""
    get_store().delete_auth_session(session_id=session_id)
    return LogoutResponse(success=True)


def _unauthorized() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated. Start at /auth/login.",
        headers={"WWW-Authenticate": "Bearer"},
    )


def _issue_token_response(
    *,
    config: OidcConfig,
    token: str,
    session_id: str | None = None,
) -> TokenResponse:
    claims = decode_app_token(config=config, token=token)
    if claims is not None:
        _grant_self_chat_access(claims)
        if session_id is not None:
            get_store().authenticate_session(
                session_id=session_id,
                token=token,
                claims=claims,
            )
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


def _require_known_session(session_id: str | None) -> None:
    if session_id is None:
        return
    if get_store().get_auth_session(session_id=session_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Unknown auth session.",
        )


def _session_login_url(*, config: OidcConfig, session_id: str) -> str:
    return (
        f"{config.service_base_url.rstrip('/')}/auth/login?"
        f"{urlencode({'session_id': session_id})}"
    )


def _session_status_url(*, config: OidcConfig, session_id: str) -> str:
    return f"{config.service_base_url.rstrip('/')}/auth/sessions/{session_id}"


def _login_page_html(
    *,
    client_id: str,
    nonce: str,
    origin: str,
    session_id: str | None,
) -> str:
    session_hint = (
        f"Use X-Session-ID: {session_id} on /chat/*."
        if session_id is not None
        else "Use the returned Bearer token on /chat/*."
    )
    client_id_json = json.dumps(client_id)
    nonce_json = json.dumps(nonce)
    origin_json = json.dumps(origin)
    session_hint_json = json.dumps(session_hint)
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Telegram Login</title>
  <style>
    body {{ font-family: sans-serif; margin: 2rem; line-height: 1.5; }}
    button {{ padding: 0.7rem 1rem; cursor: pointer; }}
    pre {{ white-space: pre-wrap; word-break: break-word; }}
  </style>
</head>
<body>
  <h1>Sign in with Telegram</h1>
  <p>This authenticates your API session. Chat operations remain bot-scoped.</p>
  <button id="telegram-login" type="button">Continue with Telegram</button>
  <pre id="status"></pre>
  <script src="https://oauth.telegram.org/js/telegram-login.js?3"></script>
  <script>
    const clientId = Number({client_id_json});
    const nonce = {nonce_json};
    const origin = {origin_json};
    const sessionHint = {session_hint_json};
    const statusBox = document.getElementById("status");
    function show(message) {{
      statusBox.textContent = message;
    }}
    async function finishLogin(data) {{
      if (!data || data.error) {{
        show(data && data.error ? data.error : "Telegram login was cancelled.");
        return;
      }}
      if (!data.id_token) {{
        show("Telegram did not return an id_token.");
        return;
      }}
      const response = await fetch("/auth/callback", {{
        method: "POST",
        headers: {{"content-type": "application/json"}},
        body: JSON.stringify({{id_token: data.id_token, nonce}}),
      }});
      const body = await response.json();
      if (!response.ok) {{
        show(body.detail || "Login failed.");
        return;
      }}
      show("Login complete. " + sessionHint);
    }}
    Telegram.Login.init({{
      client_id: clientId,
      request_access: ["write"],
      nonce,
    }}, finishLogin);
    document.getElementById("telegram-login").addEventListener("click", () => {{
      const openPopup = window.open;
      window.open = function(url, target, features) {{
        if (
          typeof url === "string" &&
          url.startsWith("https://oauth.telegram.org/auth?")
        ) {{
          const authUrl = new URL(url);
          authUrl.searchParams.set("origin", origin);
          url = authUrl.toString();
        }}
        return openPopup.call(window, url, target, features);
      }};
      try {{
        Telegram.Login.open(finishLogin);
      }} finally {{
        window.open = openPopup;
      }}
    }});
  </script>
</body>
</html>
"""
