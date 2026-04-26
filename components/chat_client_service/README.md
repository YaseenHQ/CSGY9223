# Chat Client Service

`chat_client_service` is the HW2/HW3 FastAPI deployment unit for the shared chat
API. In this branch, the Telegram backend is bot-scoped and uses the official
Telegram Bot API.

## Endpoints

- `GET /health`
- `POST /auth/sessions`
- `GET /auth/login`
- `GET /auth/login/config`
- `GET /auth/callback`
- `POST /auth/callback`
- `POST /auth/telegram-login`
- `GET /auth/me`
- `GET /auth/sessions/{session_id}`
- `DELETE /auth/sessions/{session_id}`
- `POST /chat/messages`
- `GET /chat/messages`
- `GET /chat/messages/{message_id}`
- `DELETE /chat/messages/{message_id}`
- `GET /chat/channels`
- `GET /chat/channels/{channel_id}`
- `POST /telegram/webhook`

## Local Run

```bash
uv run uvicorn chat_client_service.app:app --reload
```

OpenAPI schema is available at `/openapi.json`.

## CloudWatch Telemetry

Request telemetry is emitted as structured EMF-style JSON.

- By default, the service writes telemetry to the console.
- If `CHAT_CLIENT_CLOUDWATCH_ENABLED=true`, the service sends the same events
  directly to AWS CloudWatch Logs.

Telemetry environment variables:

- `CHAT_CLIENT_CLOUDWATCH_ENABLED`
- `CHAT_CLIENT_CLOUDWATCH_LOG_GROUP`
- `CHAT_CLIENT_CLOUDWATCH_STREAM_NAME`
- `CHAT_CLIENT_CLOUDWATCH_REGION`
- `CHAT_CLIENT_CLOUDWATCH_USE_QUEUES`
- `CHAT_CLIENT_CLOUDWATCH_SEND_INTERVAL`

AWS credentials should come from standard AWS SDK environment variables:

- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`
- `AWS_SESSION_TOKEN`
- `AWS_REGION` or `AWS_DEFAULT_REGION`

## Runtime Configuration

Required service-owned variables:

- `TELEGRAM_BOT_TOKEN`: bot token from [BotFather](https://t.me/BotFather)
- `SERVICE_BASE_URL`: public service URL, for example `https://<service>.onrender.com`
- `CHAT_CLIENT_STORE_PATH`: SQLite path; use `/var/data/chat_client.sqlite3` on Render

Recommended deployment variables:

- `TELEGRAM_UPDATE_MODE=polling`
- `TELEGRAM_POLL_INTERVAL_SECONDS=3`

Optional variables:

- `APP_SESSION_SECRET`: signing override for local service tokens; defaults to bot token
- `APP_SESSION_TTL_SECONDS`: local bearer/session TTL; defaults to `3600`
- `TELEGRAM_OIDC_CLIENT_ID`: optional override for Telegram login client id
- `TELEGRAM_OIDC_CLIENT_SECRET`: optional OIDC code-flow secret
- `TELEGRAM_WEBHOOK_SECRET`: optional webhook hardening when using `/telegram/webhook`
- `TELEGRAM_BOT_API_BASE_URL`: override only for a custom Bot API server

## Auth Flow

This service now supports the Telegram login paths documented in
[Log In With Telegram](https://core.telegram.org/bots/telegram-login).

Primary session-first API-client flow:

1. `POST /auth/sessions`
2. Open the returned `login_url`
3. Complete Telegram login in the browser
4. Poll `GET /auth/sessions/{session_id}` until `authenticated=true`
5. Use `X-Session-ID: <session_id>` on `/chat/*`

Available auth callbacks:

1. `GET /auth/login`
2. `GET /auth/login?flow=code` forces Authorization Code + PKCE when
   `TELEGRAM_OIDC_CLIENT_SECRET` is configured
3. `GET /auth/login/config` supports custom frontends using Telegram's Login library
4. `GET /auth/callback` completes OIDC code flow
5. `POST /auth/callback` accepts `id_token` + `nonce`
6. `POST /auth/telegram-login` accepts signed `tgAuthResult`

Browser clients can also rely on the HTTP-only `chat_client_session` cookie set
by the auth callbacks. API clients can also use the returned Bearer token
directly. Logout deletes the cookie and session-backed `X-Session-ID`; direct
Bearer tokens remain valid until `APP_SESSION_TTL_SECONDS` expires.

## Chat Semantics

This implementation is bot-scoped:

- `POST /chat/messages` sends through the configured bot
- `GET /chat/messages` returns bot-observed or bot-sent messages stored locally
- `GET /chat/channels` returns chats known to the bot
- `channel_id="me"` means the logged-in user's direct chat with the bot

Message responses use opaque `channel_id:message_id` ids. Pass that value back
to `DELETE /chat/messages/{message_id}` when deleting.

If an example uses `OSSHWBOTTEST`, replace it with any group or channel where
the bot is present. `me` means the logged-in user's direct chat with the bot.

## Polling vs Webhook

Telegram only delivers bot updates one way at a time:

- `TELEGRAM_UPDATE_MODE=polling`: service starts a background `getUpdates` poller
- `TELEGRAM_UPDATE_MODE=webhook`: Telegram must POST to `/telegram/webhook`

For Render, the recommended path is polling plus a persistent disk. Webhook mode
is still available, and `TELEGRAM_WEBHOOK_SECRET` is optional rather than
required.
