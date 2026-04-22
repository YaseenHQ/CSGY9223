# Telegram Client Implementation

This package provides a Telegram Bot API implementation of `chat_client_api`.

## Purpose

- Register a concrete implementation via dependency injection
- Keep the interface (`chat_client_api`) free of Telegram-specific details
- Use the official Bot API for bot-scoped chat operations

## Usage

```python
import telegram_client_impl  # Registers factory injection
from chat_client_api import get_client

client = get_client(interactive=False)
```

## Drop-In Use

This folder is intended to work as a standalone component in another project:

1. Copy `components/telegram_client_impl/` into the target repo.
2. Add it as a workspace member or path dependency.
3. Ensure the target project depends on the shared chat API package that exposes
   the `chat_client_api` module with `ChatClient`, `Message`, `Channel`, and
   `register_client`.
4. Set `TELEGRAM_BOT_TOKEN`.
5. Import `telegram_client_impl` before calling `chat_client_api.get_client()`.

No `chat_client_service` package, Telegram API ID/hash, Telethon dependency, or
Telegram user session string is required by this implementation component.

For `get_channels()` and `get_messages()` to include messages that were not sent
through this client, the host app should pass Telegram webhook payloads into the
implementation store:

```python
import telegram_client_impl

telegram_client_impl.record_update(update_payload)
```

If no webhook is configured for the bot, reads make one short `getUpdates` poll
before returning local state. Telegram disables `getUpdates` while a webhook is
active, so deployed services should still use webhooks for reliable delivery.

## Environment Variables

The implementation reads:

- `TELEGRAM_BOT_TOKEN`
- `CHAT_CLIENT_STORE_PATH` (optional, defaults to `.data/chat_client.sqlite3`)
- `TELEGRAM_BOT_API_BASE_URL` (optional, defaults to `https://api.telegram.org`)

The hosted service also uses Telegram OIDC variables documented in the root
README. API consumers should not configure Telegram API ID/hash values, user
session strings, or their own service.

## Runtime Behavior

Reads and channel lists are based on bot-observed state, not arbitrary Telegram
user history. Telegram keeps undelivered updates for at most 24 hours.

Deletion uses Bot API `deleteMessage` and may fail when Telegram rejects it
because of message age, service-message limits, chat type, or missing bot
administrator rights.
