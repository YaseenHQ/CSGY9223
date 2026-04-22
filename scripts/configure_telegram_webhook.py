"""Configure Telegram Bot API webhook for the deployed chat service."""

from __future__ import annotations

import os
import sys
from typing import Any

import httpx

DEFAULT_ALLOWED_UPDATES = [
    "message",
    "edited_message",
    "channel_post",
    "edited_channel_post",
    "my_chat_member",
]


def main() -> int:
    """Register SERVICE_BASE_URL/telegram/webhook with Telegram."""
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    service_base_url = os.getenv("SERVICE_BASE_URL")
    secret = os.getenv("TELEGRAM_WEBHOOK_SECRET")
    if not bot_token or not service_base_url:
        sys.stderr.write("TELEGRAM_BOT_TOKEN and SERVICE_BASE_URL are required\n")
        return 2

    bot_api_base_url = os.getenv(
        "TELEGRAM_BOT_API_BASE_URL", "https://api.telegram.org"
    )
    webhook_url = f"{service_base_url.rstrip('/')}/telegram/webhook"
    payload: dict[str, object] = {
        "url": webhook_url,
        "allowed_updates": _allowed_updates_from_env(),
    }
    if secret:
        payload["secret_token"] = secret
    if _env_bool("TELEGRAM_WEBHOOK_DROP_PENDING_UPDATES"):
        payload["drop_pending_updates"] = True

    response = httpx.post(
        f"{bot_api_base_url.rstrip('/')}/bot{bot_token}/setWebhook",
        json=payload,
        timeout=10,
    )
    response.raise_for_status()
    body: Any = response.json()
    if not isinstance(body, dict) or body.get("ok") is not True:
        sys.stderr.write(f"Telegram setWebhook failed: {body}\n")
        return 1

    sys.stdout.write(f"Telegram webhook configured for {webhook_url}\n")
    return 0


def _allowed_updates_from_env() -> list[str]:
    raw = os.getenv("TELEGRAM_WEBHOOK_ALLOWED_UPDATES")
    if raw is None:
        return DEFAULT_ALLOWED_UPDATES
    return [item.strip() for item in raw.split(",") if item.strip()]


def _env_bool(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "on"}


if __name__ == "__main__":
    raise SystemExit(main())
