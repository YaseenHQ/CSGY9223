"""FastAPI application for the chat client service scaffold."""

from fastapi import FastAPI
from pydantic import BaseModel

from chat_client_service.routers.auth import router as auth_router
from chat_client_service.routers.chat import router as chat_router


class HealthResponse(BaseModel):
    """Health endpoint response payload."""

    status: str


app = FastAPI(
    title="Chat Client Service",
    description="Scaffold FastAPI service for HW2.",
    version="0.1.0",
)


@app.get("/health")
def health() -> HealthResponse:
    """Return service health status."""
    return HealthResponse(status="ok")


app.include_router(auth_router)
app.include_router(chat_router)
