"""FastAPI application for Telegram OIDC and Bot API chat operations."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.responses import HTMLResponse, JSONResponse

from chat_client_service.config import load_environment
from chat_client_service.middleware.telemetry import TelemetryMiddleware
from chat_client_service.models import HealthResponse
from chat_client_service.routers.auth import router as auth_router
from chat_client_service.routers.chat import router as chat_router
from chat_client_service.routers.telegram import router as telegram_router
from chat_client_service.update_poller import (
    TelegramUpdatePoller,
    poll_interval_seconds,
    should_start_update_poller,
)
from telegram_client_impl.client import get_bot_login_target

LOGGER = logging.getLogger(__name__)

load_environment()
logging.getLogger("httpx").setLevel(logging.WARNING)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Start optional background services for the FastAPI app."""
    poller: TelegramUpdatePoller | None = None
    if should_start_update_poller():
        poller = TelegramUpdatePoller(interval_seconds=poll_interval_seconds())
        poller.start()
    try:
        yield
    finally:
        if poller is not None:
            poller.stop()


app = FastAPI(
    title="Chat Client Service",
    description="Telegram OIDC login with bot-scoped chat operations.",
    version="0.1.0",
    lifespan=lifespan,
)
app.add_middleware(TelemetryMiddleware)


@app.exception_handler(Exception)
async def unhandled_exception_handler(
    request: Request, _exc: Exception
) -> JSONResponse:
    """Return a JSON 500 response for any unhandled exception."""
    LOGGER.exception(
        "Unhandled exception in %s %s",
        request.method,
        request.url.path,
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal server error."},
    )


@app.get("/health")
def health() -> HealthResponse:
    """Return service health status."""
    return HealthResponse(status="ok")


@app.get("/", response_model=None)
def root() -> HTMLResponse:
    """Handle Telegram auth fragments that browsers do not send to the server."""
    bot_username, bot_start_url = get_bot_login_target()
    return HTMLResponse(
        _root_fragment_handler_html(
            bot_username=bot_username,
            bot_start_url=bot_start_url,
        )
    )


def _root_fragment_handler_html(
    *,
    bot_username: str | None,
    bot_start_url: str | None,
) -> str:
    bot_username_js = _js_string(bot_username)
    bot_start_url_js = _js_string(bot_start_url)
    return """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Telegram Login</title>
</head>
<body>
  <pre id="status">Completing Telegram login...</pre>
  <p id="bot-start-hint"></p>
  <script>
    const statusBox = document.getElementById("status");
    const botStartHint = document.getElementById("bot-start-hint");
    const botUsername = __BOT_USERNAME__;
    const botStartUrl = __BOT_START_URL__;
    const fragment = new URLSearchParams(window.location.hash.slice(1));
    const authResult = fragment.get("tgAuthResult");
    const state = sessionStorage.getItem("telegram_auth_state") ||
      localStorage.getItem("telegram_auth_state");
    const sessionId = sessionStorage.getItem("telegram_auth_session_id") ||
      localStorage.getItem("telegram_auth_session_id");
    function renderBotStartHint() {
      if (!botStartHint || !botUsername || !botStartUrl) {
        return;
      }
      botStartHint.textContent = "";
      botStartHint.append(
        document.createTextNode("If Telegram says chat not found, open "),
        Object.assign(document.createElement("a"), {
          href: botStartUrl,
          target: "_blank",
          rel: "noreferrer",
          textContent: "@" + botUsername,
        }),
        document.createTextNode(" and press Start.")
      );
    }
    renderBotStartHint();
    if (!authResult) {
      statusBox.textContent = "Chat Client Service";
    } else {
      async function responseBody(response) {
        const contentType = response.headers.get("content-type") || "";
        if (!contentType.includes("application/json")) {
          return {detail: "Login failed. Please retry."};
        }
        try {
          return await response.json();
        } catch {
          return {detail: "Login failed. Please retry."};
        }
      }
      fetch("/auth/telegram-login", {
        method: "POST",
        credentials: "same-origin",
        headers: {"content-type": "application/json"},
        body: JSON.stringify({
          auth_result: authResult,
          state,
          session_id: sessionId,
        }),
      }).then(async (response) => {
        const body = await responseBody(response);
        if (!response.ok) {
          statusBox.textContent = body.detail || "Login failed. Please retry.";
          return;
        }
        sessionStorage.removeItem("telegram_auth_state");
        sessionStorage.removeItem("telegram_auth_session_id");
        localStorage.removeItem("telegram_auth_state");
        localStorage.removeItem("telegram_auth_session_id");
        window.history.replaceState(null, "", "/");
        statusBox.textContent =
          "Login complete. You can close this tab and return to your API client.";
        if (window.opener && !window.opener.closed) {
          window.opener.postMessage(
            {
              type: "telegram-auth-complete",
              sessionId: sessionId,
            },
            window.location.origin
          );
        }
      }).catch(() => {
        statusBox.textContent = "Login failed. Please retry.";
      });
    }
  </script>
</body>
</html>
""".replace("__BOT_USERNAME__", bot_username_js).replace(
        "__BOT_START_URL__", bot_start_url_js
    )


def _js_string(value: str | None) -> str:
    if value is None:
        return "null"
    escaped = (
        value.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\n", "\\n")
        .replace("\r", "\\r")
        .replace("</", "<\\/")
    )
    return f'"{escaped}"'


app.include_router(auth_router)
app.include_router(chat_router)
app.include_router(telegram_router)
