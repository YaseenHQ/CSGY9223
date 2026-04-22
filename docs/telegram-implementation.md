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

Primary Telegram Login library path:

- `POST /auth/sessions` creates a pending service session.
- `GET /auth/login/config?session_id=...` returns a server-generated `nonce` and Telegram
  Login `client_id`.
- A frontend passes those values to `Telegram.Login.init(...)`.
- Telegram returns an `id_token` to the frontend callback.
- `POST /auth/callback` verifies that `id_token` server-side, checks the nonce,
  authenticates the session, and returns this service's Bearer token.
- Adapter-style clients poll `GET /auth/sessions/{session_id}` and use
  `X-Session-ID` on `/chat/*`; direct Bearer tokens remain supported.

The default `GET /auth/login` route serves a minimal Telegram Login page. OIDC
Authorization Code Flow is also available for OIDC-compatible clients:

- `GET /auth/login?flow=code` redirects users to Telegram OIDC.
- `GET /auth/callback` exchanges the code, validates `id_token`, and checks the
  OIDC nonce.
- The service authenticates the bound session when `session_id` was supplied and
  issues its own Bearer token for compatibility.

Required service-owned Render environment variables:

- `TELEGRAM_BOT_TOKEN`
- `SERVICE_BASE_URL`
- `TELEGRAM_WEBHOOK_SECRET`
- `CHAT_CLIENT_STORE_PATH`

Optional deployment settings:

- `APP_SESSION_SECRET` (optional signing override; defaults to bot token)
- `APP_SESSION_TTL_SECONDS` (optional)
- `TELEGRAM_OIDC_CLIENT_ID` (optional override; defaults to bot token numeric id)
- `TELEGRAM_OIDC_CLIENT_SECRET` (required only for `GET /auth/login?flow=code`)
- `TELEGRAM_WEBHOOK_ALLOWED_UPDATES` (optional comma-separated update types)
- `TELEGRAM_WEBHOOK_DROP_PENDING_UPDATES` (optional webhook setup flag)

API consumers do not need Telegram API ID/hash values, user session strings, or
their own service deployment.

## Bot-Scoped Chat Behavior

Bot API does not expose arbitrary user chat history or user dialog listing.
Therefore:

- `POST /chat/messages` sends through the service bot.
- `GET /chat/messages` returns messages the bot observed or sent.
- `GET /chat/channels` returns chats known to the bot.
- `DELETE /chat/messages/{message_id}` works when Telegram allows the bot to
  delete that message.

The webhook is what makes reads work. Configure it after deploy:

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
webhooks are mutually exclusive. The webhook setup script registers explicit
`allowed_updates` so Telegram sends the update types this service records:
`message`, `edited_message`, `channel_post`, `edited_channel_post`, and
`my_chat_member`.

`DELETE /chat/messages/{message_id}` calls Bot API `deleteMessage`; Telegram can
still reject deletion for age, service-message, channel, or administrator-rights
constraints. Message responses return opaque ids in `channel_id:message_id`
form, so callers can pass the returned id directly to the delete route.
