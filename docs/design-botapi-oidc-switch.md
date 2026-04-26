# Design: Bot API + OIDC Switch

## Context

The original Telegram implementation in this course workspace was built on
Telethon and MTProto user-session behavior. That created two problems for the
later homework stages:

1. The runtime model behaved more like a full Telegram client than a shared,
   plug-and-play chat vertical implementation.
2. The auth story did not align cleanly with the HW3 expectation of a standards-
   based OAuth2/OIDC login flow.

This branch keeps the shared `chat_client_api` contract intact while switching
the Telegram implementation to the official Bot API and restoring Telegram's
documented OpenID Connect login flow.

## Why Bot API

The Bot API is the correct abstraction for this project scope:

- it is service-owned and deployable on Render without per-user Telegram
  session strings
- it maps naturally to a shared API service used by other teams
- it supports send/delete directly and receive flows through `getUpdates` or
  webhooks
- it avoids Telethon's event-loop, MTProto, and user-session operational
  complexity

The tradeoff is explicit: Bot API is bot-scoped. It does not expose arbitrary
Telegram user history or dialog listing. Reads therefore return messages the bot
observed through polling, webhooks, or service sends.

## Why OIDC

Telegram now documents
[Log In With Telegram](https://core.telegram.org/bots/telegram-login), including:

- OpenID Connect discovery
- Authorization Code Flow with PKCE
- JWKS-backed `id_token` verification
- hosted Telegram Login page / Login library

That gives this implementation a standards-based login path while keeping the
service-owned local session abstraction required by the rest of the workspace.

## Final Architecture

### Runtime layer

- `telegram_client_impl` uses the Bot API through `httpx`
- `store.py` persists bot-observed channels, messages, access grants, auth
  sessions, OIDC state, and polling offsets in SQLite
- `update_poller.py` provides singleton background polling when
  `TELEGRAM_UPDATE_MODE=polling`
- `/telegram/webhook` remains available for webhook deployments

### Auth layer

- `oidc.py` owns Telegram OIDC config, PKCE state, token exchange, JWKS
  validation, and local service token issuance
- `routers/auth.py` exposes session-oriented HTTP endpoints:
  - `POST /auth/sessions`
  - `GET /auth/login`
  - `GET /auth/login/config`
  - `GET /auth/callback`
  - `POST /auth/callback`
  - `POST /auth/telegram-login`
  - `GET /auth/sessions/{session_id}`
  - `DELETE /auth/sessions/{session_id}`
  - `GET /auth/me`
- `POST /auth/verify` is retained only as a compatibility bridge for earlier
  browser/manual flows

### Service session model

- Telegram login proves the caller's Telegram identity
- the service then issues its own short-lived Bearer token
- adapter/manual clients primarily use `X-Session-ID`
- browser clients can use the `chat_client_session` HTTP-only cookie

This keeps `/chat/*` stable while avoiding provider-specific auth leakage into
consumer code.

## Shared-API Compatibility

No `ChatClient` method signatures were changed. The Telegram implementation was
swapped under the existing interface:

- sends and deletes go through the bot
- reads come from persisted bot-observed state
- opaque message ids remain `channel_id:message_id`
- `channel_id="me"` maps to the logged-in user's direct chat with the bot

That means teammates and downstream integrations keep the same `/chat/*`
surface while the Telegram internals become easier to deploy and reason about.

## Deployment Model

Recommended Render deployment:

- `TELEGRAM_BOT_TOKEN`
- `SERVICE_BASE_URL`
- `CHAT_CLIENT_STORE_PATH=/var/data/chat_client.sqlite3`
- persistent disk mounted at `/var/data`
- `TELEGRAM_UPDATE_MODE=polling`

Optional OIDC overrides:

- `TELEGRAM_OIDC_CLIENT_ID`
- `TELEGRAM_OIDC_CLIENT_SECRET`

If explicit OIDC client credentials are configured, the service can force
Authorization Code + PKCE. Otherwise, it still supports Telegram's hosted login
page / Login library while keeping the same local session contract.

## Limitations

- This is not a full Telegram account client.
- Reads are limited to chats/messages the bot can observe.
- `getUpdates` and webhooks are mutually exclusive, per Telegram.
- Free-tier Render sleep can still delay update ingestion if the service is not
  awake.

These are acceptable constraints for a bot-scoped shared chat vertical and are
more honest than pretending the Bot API can reproduce full Telegram user-client
behavior.
