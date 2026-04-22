"""FastAPI application for Telegram OIDC and Bot API chat operations."""

from fastapi import FastAPI
from fastapi.responses import HTMLResponse

from chat_client_service.models import HealthResponse
from chat_client_service.routers import auth, chat, telegram

app = FastAPI(
    title="Chat Client Service",
    description="Telegram OIDC login with bot-scoped chat operations.",
    version="0.1.0",
)

app.include_router(auth.router)
app.include_router(chat.router)
app.include_router(telegram.router)


@app.get("/", response_model=None)
def root() -> HTMLResponse:
    """Handle Telegram auth fragments that browsers do not send to the server."""
    return HTMLResponse(
        """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Telegram Login</title>
</head>
<body>
  <pre id="status">Completing Telegram login...</pre>
  <script>
    const statusBox = document.getElementById("status");
    const fragment = new URLSearchParams(window.location.hash.slice(1));
    const authResult = fragment.get("tgAuthResult");
    const state = sessionStorage.getItem("telegram_auth_state");
    const sessionId = sessionStorage.getItem("telegram_auth_session_id");
    if (!authResult) {
      statusBox.textContent = "Chat Client Service";
    } else {
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
        const body = await response.json();
        if (!response.ok) {
          statusBox.textContent = body.detail || "Login failed.";
          return;
        }
        sessionStorage.removeItem("telegram_auth_state");
        sessionStorage.removeItem("telegram_auth_session_id");
        statusBox.textContent = "Login complete. Return to your API client.";
        window.history.replaceState(null, "", "/");
      });
    }
  </script>
</body>
</html>
"""
    )


@app.get("/health")
def health() -> HealthResponse:
    """Return service health status."""
    return HealthResponse(status="ok")
