# Telegram Bot API Implementation

## Package Layout

- `components/telegram_client_impl/pyproject.toml`
- `components/telegram_client_impl/README.md`
- `components/telegram_client_impl/src/telegram_client_impl/*.py`
- `components/chat_client_service/src/chat_client_service/*.py`

## Injection Behavior

When `telegram_client_impl` is imported, it registers implementation factories into
`chat_client_api`:

- `chat_client_api.get_client`
- `chat_client_api.get_message`

This allows consumers to code against the interface while swapping implementation
by import.

## Authentication

This branch implements both login paths documented on Telegram's
[Log In With Telegram](https://core.telegram.org/bots/telegram-login) page.

Primary session path:

- `POST /auth/sessions` creates a pending service session.
- `GET /auth/login?session_id=...&flow=page` starts the hosted Telegram Login
  page using the service bot's login Client ID.
- `GET /auth/login/config?session_id=...` remains available for custom
  frontends using Telegram's Login library.
- The config endpoint returns a server-generated `nonce` and Telegram Login
  `client_id`.
- A frontend passes those values to `Telegram.Login.init(...)`.
- Telegram returns either an `id_token` or a signed login payload to the browser.
- `POST /auth/callback` or `POST /auth/telegram-login` verifies that payload,
  authenticates the session, and returns this service's Bearer token.
- Adapter-style clients poll `GET /auth/sessions/{session_id}` and use
  `X-Session-ID` on `/chat/*`; direct Bearer tokens remain supported.

OIDC Authorization Code Flow is still available when explicit client
credentials are configured:

- `GET /auth/login?flow=code` redirects users to Telegram OIDC.
- `GET /auth/login?flow=page` serves the fallback hosted Telegram Login page.
- `GET /auth/callback` exchanges the code, validates `id_token`, and checks the
  OIDC nonce.
- The service authenticates the bound session when `session_id` was supplied and
  issues its own Bearer token for compatibility.

Required service-owned Render environment variables:

- `TELEGRAM_BOT_TOKEN`
- `SERVICE_BASE_URL`
- `CHAT_CLIENT_STORE_PATH`

Optional deployment settings:

- `APP_SESSION_SECRET` (optional signing override; defaults to bot token)
- `APP_SESSION_TTL_SECONDS` (optional)
- `TELEGRAM_OIDC_CLIENT_ID` (optional override; defaults to bot token numeric id)
- `TELEGRAM_OIDC_CLIENT_SECRET` (optional override only for explicit code flow)
- `TELEGRAM_WEBHOOK_SECRET` (optional webhook hardening)
- `TELEGRAM_WEBHOOK_ALLOWED_UPDATES` (optional comma-separated update types)
- `TELEGRAM_WEBHOOK_DROP_PENDING_UPDATES` (optional webhook setup flag)
- `TELEGRAM_UPDATE_MODE` (`polling` keeps ingesting messages while the server
  runs; `webhook` relies on `/telegram/webhook`)
- `TELEGRAM_POLL_INTERVAL_SECONDS` (optional polling interval)

API consumers do not need Telegram API ID/hash values, user session strings, or
their own service deployment.

## Bot-Scoped Chat Behavior

Bot API does not expose arbitrary user chat history or user dialog listing.
Therefore:

- `POST /chat/messages` sends through the service bot.
- `GET /chat/messages` returns messages the bot observed, pulled while no
  webhook is configured, or sent. Optional `cursor=<message_id>` returns newer
  stored messages for incremental consumers.
- `GET /chat/messages/{message_id}` returns one observed or sent message by
  opaque id.
- `GET /chat/channels` returns chats known to the bot.
- `GET /chat/channels/{channel_id}` returns one known chat.
- `DELETE /chat/messages/{message_id}` works when Telegram allows the bot to
  delete that message.

The simplest Render path is `TELEGRAM_UPDATE_MODE=polling`, which starts a
background Bot API long poller while the server is running and stores updates in
`CHAT_CLIENT_STORE_PATH`. Webhook deployment is also supported. Configure it
after deploy:

```bash
uv run python scripts/configure_telegram_webhook.py
```

For group/channel access, the bot must be present in the chat. The webhook
records observed messages and grants access to their senders; when no grant is
cached, the service asks Bot API `getChatMember` to verify that the logged-in
Telegram user belongs to that chat. Telegram only guarantees `getChatMember` for
other users when the bot is an administrator in the chat. Replace `OSSHWBOTTEST`
with any group or channel used for testing. `channel_id=me` targets the
logged-in user's direct chat with the bot.

Telegram stores undelivered updates for at most 24 hours, and `getUpdates` and
webhooks are mutually exclusive. When no webhook is configured, polling mode and
read endpoints use `getUpdates` before reading the local store. Once a webhook is
active, Telegram will not allow polling, so delivery depends on the webhook URL
and optional secret being correct. The webhook setup script registers explicit
`allowed_updates` so Telegram sends the update types this service records:
`message`, `edited_message`, `channel_post`, `edited_channel_post`, and
`my_chat_member`.

`DELETE /chat/messages/{message_id}` calls Bot API `deleteMessage`; Telegram can
still reject deletion for age, service-message, channel, or administrator-rights
constraints. Message responses return opaque ids in `channel_id:message_id`
form, so callers can pass the returned id directly to the delete route.
