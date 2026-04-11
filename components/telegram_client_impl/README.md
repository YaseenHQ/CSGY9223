# Telegram Client Implementation

This package implements the shared vertical [`chat_client_api`](https://github.com/HarshithKoriRaj/Shared-API) **`ChatClient`** for Telegram (Telethon).

## Registration

On import, the package calls `register_client(get_client_impl)` so `from chat_client_api import get_client` returns a configured `TelegramClient`.

## Usage

```python
import telegram_client_impl
from chat_client_api import get_client

client = get_client()
```

## Environment variables

- `TELEGRAM_API_ID`
- `TELEGRAM_API_HASH`
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_SESSION_NAME` (optional)
- `TELEGRAM_INTERACTIVE` (optional; `1` / `true` / `yes` — see root README)

## Opaque message IDs

Telegram exposes opaque IDs as `<chat_id>:<telegram_message_id>`. Use `split(":", 1)` when
decoding. `get_message`, `delete_message`, and mapped `Message.message_id` values follow this
format.

## Behavior

- `get_messages` returns a `list[Message]`; optional API `cursor` is ignored.
- `delete_message(message_id) -> None` raises `ValueError` on failure (per shared contract).
- `get_channel` / `get_message` raise `ValueError` when the entity or message is missing.

No secrets are hardcoded.
