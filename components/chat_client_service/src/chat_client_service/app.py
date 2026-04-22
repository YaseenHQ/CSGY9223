"""FastAPI application for Telegram OIDC and Bot API chat operations."""

from fastapi import FastAPI

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


@app.get("/health")
def health() -> HealthResponse:
    """Return service health status."""
    return HealthResponse(status="ok")
