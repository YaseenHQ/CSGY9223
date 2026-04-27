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

Minimal working Render setup:

- `TELEGRAM_BOT_TOKEN`: bot token from [BotFather](https://t.me/BotFather)
- `SERVICE_BASE_URL`: public service URL, for example `https://<service>.onrender.com`

For the current migration branch, that is the intended baseline. The Render
blueprint already supplies defaults for the rest.

Blueprint defaults:

- `CHAT_CLIENT_STORE_PATH=/tmp/chat_client.sqlite3`
- `TELEGRAM_UPDATE_MODE=polling`
- `TELEGRAM_POLL_INTERVAL_SECONDS=3`
- `APP_SESSION_TTL_SECONDS=3600`

On the free Render plan, keep those defaults unless you have a specific reason
to override them.

Storage note:

- `/tmp/chat_client.sqlite3` works on free Render because it is writable
- it is ephemeral, so auth sessions and stored messages can disappear on restart
- if you later move to a paid plan with a persistent disk, switch to
  `/var/data/chat_client.sqlite3`

Optional variables:

- `APP_SESSION_SECRET`: signing override for local service tokens; defaults to bot token
- `APP_SESSION_TTL_SECONDS`: local bearer/session TTL; defaults to `3600`
- `TELEGRAM_OIDC_CLIENT_ID`: optional override for Telegram login client id
- `TELEGRAM_OIDC_CLIENT_SECRET`: optional OIDC code-flow secret
- `TELEGRAM_WEBHOOK_SECRET`: optional webhook hardening when using `/telegram/webhook`
- `TELEGRAM_BOT_API_BASE_URL`: override only for a custom Bot API server

Do not set optional variables unless you need them. The minimal Render path is
the least error-prone path.

## BotFather Setup

This service assumes the developer has already created a Telegram bot in
[@BotFather](https://t.me/BotFather).

Base setup:

1. Run `/newbot`
2. choose the bot name and username
3. copy the generated token into `TELEGRAM_BOT_TOKEN`
4. confirm the deployed service is using the same bot identity the user will
   open in Telegram

If you want the service to show the bot handle without calling `getMe` at
runtime, set:

- `TELEGRAM_BOT_USERNAME`

That value should be the plain username, with or without a leading `@`.

Privacy mode:

- not required for private bot-user chats
- required to be **disabled** if you want the bot to observe ordinary group
  messages instead of only commands/replies/messages explicitly directed at it

BotFather command path to disable privacy:

1. open [@BotFather](https://t.me/BotFather)
2. run `/setprivacy`
3. select the bot
4. choose `Disable`

Equivalent menu path:

1. `/start`
2. select the bot
3. `Bot Settings`
4. `Group Privacy`
5. turn it off

Telegram’s official behavior summary:

- all bots receive private-chat messages
- bots with privacy disabled receive ordinary group messages
- bots with privacy enabled only receive relevant group commands/replies

References:

- [Bots FAQ](https://core.telegram.org/bots/faq)
- [Privacy Mode](https://core.telegram.org/bots/features)

## Auth Flow

This service now supports the Telegram login paths documented in
[Log In With Telegram](https://core.telegram.org/bots/telegram-login).

Primary session-first API-client flow:

1. `POST /auth/sessions`
2. Open the returned `login_url`
   The response also includes `bot_username` and `bot_start_url` so the user can
   open the correct bot in Telegram and press Start if the bot has not chatted
   with them yet.
3. Complete Telegram login in the browser
4. Poll `GET /auth/sessions/{session_id}` until `authenticated=true`
5. Use `X-Session-ID: <session_id>` on `/chat/*`

If the returned session payload includes `bot_username` / `bot_start_url`, use
that exact bot identity when opening Telegram. The login only proves who the
user is. It does not guarantee the configured bot can already DM that user.
For `channel_id="me"`, the user may still need to open the bot and press
Start once before `POST /chat/messages` can succeed.

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

## PowerShell Walkthrough

This is the intended PowerShell flow for testing the hosted service end to end.

Prerequisites:

- `TELEGRAM_BOT_TOKEN` on the service must match the bot the user will open
- the user must complete Telegram login in the browser
- before sending to `channel_id="me"`, the user may need to open the bot shown
  by `bot_start_url` and press Start

Create a pending auth session:

```powershell
$base = "https://chat-client-service.onrender.com"

$session = Invoke-RestMethod `
  -Method POST `
  -Uri "$base/auth/sessions"

$session | ConvertTo-Json -Depth 5
```

The response includes:

- `session_id`
- `login_url`
- `status_url`
- optionally `bot_username`
- optionally `bot_start_url`

Open the login page:

```powershell
Start-Process $session.login_url
```

If `bot_start_url` is present and the user has never messaged that bot before,
open that link in Telegram and press Start.

Poll until authenticated:

```powershell
Invoke-RestMethod -Uri $session.status_url | ConvertTo-Json -Depth 5
```

When `authenticated` becomes `true`, use the session id on `/chat/*`:

```powershell
$headers = @{
  "X-Session-ID" = $session.session_id
}
```

Check the authenticated identity:

```powershell
Invoke-RestMethod `
  -Uri "$base/auth/me" `
  -Headers $headers | ConvertTo-Json -Depth 5
```

Send a DM through the bot:

```powershell
$sent = Invoke-RestMethod `
  -Method POST `
  -Uri "$base/chat/messages" `
  -Headers $headers `
  -ContentType "application/json" `
  -Body '{"channel_id":"me","text":"hello from powershell"}'

$sent | ConvertTo-Json -Depth 5
```

Read the DM history:

```powershell
Invoke-RestMethod `
  -Uri "$base/chat/messages?channel_id=me" `
  -Headers $headers | ConvertTo-Json -Depth 5
```

Read one message by opaque id:

```powershell
Invoke-RestMethod `
  -Uri "$base/chat/messages/$($sent.id)" `
  -Headers $headers | ConvertTo-Json -Depth 5
```

Delete one message by opaque id:

```powershell
Invoke-RestMethod `
  -Method DELETE `
  -Uri "$base/chat/messages/$($sent.id)" `
  -Headers $headers | ConvertTo-Json -Depth 5
```

Expected failure mode for a missing bot DM:

```json
{
  "detail": "This bot cannot message your private chat yet. Open @<bot_username> (<bot_start_url>), press Start, then retry. If you already did that, log in again and make sure you authenticated against the same bot."
}
```

That error means:

- Telegram login succeeded
- the service session is valid
- but the configured bot still cannot send to the user's private chat

The fix is to open the bot shown by `bot_start_url`, press Start, then retry.

## Chat Semantics

This implementation is bot-scoped:

- `POST /chat/messages` sends through the configured bot
- `GET /chat/messages` returns bot-observed or bot-sent messages stored locally
- `GET /chat/channels` returns chats known to the bot
- `channel_id="me"` means the logged-in user's direct chat with the bot
- the service does not default a missing `channel_id` to `me`; callers should
  pass `"me"` explicitly when they want the bot-user DM
- if Telegram returns `chat not found`, the user usually needs to open the
  service bot using `bot_start_url` and press Start first

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
