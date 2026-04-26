"""Telegram Bot API webhook routes."""

import hmac
from os import getenv
from typing import Annotated

from fastapi import APIRouter, Header, HTTPException, status
from pydantic import BaseModel, ConfigDict

from telegram_client_impl.store import record_update

router = APIRouter(prefix="/telegram", tags=["telegram"])


class TelegramUpdate(BaseModel):
    """Permissive model for Telegram Bot API webhook updates."""

    model_config = ConfigDict(extra="allow")

    update_id: int


@router.post("/webhook", status_code=status.HTTP_204_NO_CONTENT)
def telegram_webhook(
    update: TelegramUpdate,
    secret_token: Annotated[
        str | None,
        Header(alias="X-Telegram-Bot-Api-Secret-Token"),
    ] = None,
) -> None:
    """Record supported Telegram Bot API updates for later read endpoints."""
    expected_secret = getenv("TELEGRAM_WEBHOOK_SECRET")
    if expected_secret and not hmac.compare_digest(expected_secret, secret_token or ""):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Telegram webhook secret",
        )
    record_update(update.model_dump())
