# Getting Started

## Prerequisites

- Python 3.10 or higher
- [uv](https://docs.astral.sh/uv/) package manager for local development

## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/YaseenHQ/CSGY9223.git
   cd CSGY9223
   ```

2. Install dependencies using uv:
   ```bash
   uv sync
   ```

3. Install all dependencies (dev + docs):
   ```bash
   uv sync --all-extras
   ```

## Running Tests

```bash
uv run pytest
```

## Using Dependency Injection

```python
import telegram_client_impl
from chat_client_api import get_client

client = get_client(interactive=False)
```

## Running the Service

Users of the hosted API do not set environment variables. They create
`/auth/sessions`, open the returned `login_url`, and use `X-Session-ID` on
`/chat/*`.

Only the service deployer sets Telegram credentials. The service derives OIDC
client credentials from the bot token's `bot_id:secret` parts unless explicit
overrides are set.

```bash
export TELEGRAM_BOT_TOKEN=...
uv run uvicorn chat_client_service.app:app --host 127.0.0.1 --port 8000
```

Optional deployment settings:

- `APP_SESSION_SECRET`: override for local Bearer token signing. Defaults to
  `TELEGRAM_BOT_TOKEN`.
- `TELEGRAM_OIDC_CLIENT_ID`: optional override; defaults to the bot token's
  numeric prefix.
- `TELEGRAM_OIDC_CLIENT_SECRET`: optional override; defaults to the bot token's
  secret suffix.
- `SERVICE_BASE_URL`: required for redirect flow and webhook setup.
- `APP_SESSION_TTL_SECONDS`: local Bearer token lifetime, default `3600`.
- `CHAT_CLIENT_STORE_PATH`: SQLite path, default `.data/chat_client.sqlite3`.
- `TELEGRAM_WEBHOOK_SECRET`: optional webhook hardening. If set, Telegram must
  send the same secret header.
- `TELEGRAM_WEBHOOK_ALLOWED_UPDATES`: comma-separated update types for webhook
  setup; defaults to message, channel-post, and bot-membership updates this
  service records.
- `TELEGRAM_WEBHOOK_DROP_PENDING_UPDATES`: set `true` to discard pending updates
  when configuring the webhook.
- `TELEGRAM_BOT_API_BASE_URL`: custom Bot API server, default official API.

## Telegram Setup

1. Create a bot in [@BotFather](https://t.me/BotFather).
2. In BotFather, open Bot Settings > Web Login.
3. Add the origins where the Login library is embedded, for example your Render
   origin `https://your-service.onrender.com`.
4. Add redirect URIs such as `${SERVICE_BASE_URL}/auth/callback`.
5. If BotFather Web Login shows separate Client ID or Client Secret values, set
   `TELEGRAM_OIDC_CLIENT_ID` or `TELEGRAM_OIDC_CLIENT_SECRET`; otherwise leave
   both unset.
6. Configure the webhook after deploy:

```bash
uv run python scripts/configure_telegram_webhook.py
```

Telegram's current Login library and OIDC setup is documented in
[Log In With Telegram](https://core.telegram.org/bots/telegram-login).

For a custom frontend using Telegram's Login library:

1. Call `POST /auth/sessions`.
2. Call `GET /auth/login/config?session_id=...`.
3. Use the returned `client_id` and `nonce` in `Telegram.Login.init(...)`.
4. Send the returned `id_token` and original `nonce` to `POST /auth/callback`.
5. Use `X-Session-ID` on `/chat/*`.

## Render Deploy

Render does not need `uv`. The blueprint installs the three local packages with
`pip` and starts Uvicorn with Python:

```text
Build command:
python -m pip install --upgrade pip && python -m pip install ./components/chat_client_api ./components/telegram_client_impl ./components/chat_client_service

Start command:
python -m uvicorn chat_client_service.app:app --host 0.0.0.0 --port $PORT
```

Set only these manual Render values:

```env
TELEGRAM_BOT_TOKEN=...
SERVICE_BASE_URL=https://your-service.onrender.com
```

The blueprint sets:

```env
APP_SESSION_TTL_SECONDS=3600
CHAT_CLIENT_STORE_PATH=/var/data/chat_client.sqlite3
```

For group tests, add the bot to the chat and configure the webhook so new
messages reach `/telegram/webhook`. If the service has no cached grant for the
user yet, it checks Bot API `getChatMember` before allowing `/chat/*`; Telegram
only guarantees this for other users when the bot is an administrator in that
chat. Replace `OSSHWBOTTEST` with any group or channel where your bot is
present. Use `channel_id=me` for the logged-in user's direct chat with the bot.
Message responses return opaque ids in `channel_id:message_id` form; pass that
id to `DELETE /chat/messages/{message_id}`. The webhook rejects requests unless
`TELEGRAM_WEBHOOK_SECRET` is configured and sent by Telegram. Leaving it unset
uses Telegram's basic webhook mode without the extra secret header.

Telegram stores undelivered bot updates for at most 24 hours, and `getUpdates`
cannot be used while the webhook is configured.

## Building Documentation

```bash
uv run mkdocs serve
```
