# CS-GY-9223 Open Source

A chat client workspace with a shared vertical API and a Telegram
implementation. In this branch, the Telegram component uses the official Bot
API instead of Telethon.

## Team

**Team name:** Team 4

**Members:**

- Yukta Kulkarni — yk3213 (yuktakul04)
- Sumanth Subramanian Ramesh — sr7420
- Karthik Subramanian — ks7886
- Pranav Raj N K — pn2330
- Mohamed Yaseen Mohamed Shuaib — mm14451

## Prerequisites

- Python 3.12 or higher
- [uv](https://docs.astral.sh/uv/) package manager

## Installation

```bash
git clone https://github.com/yuktakul04/CS-GY-9223-Open-Source.git
cd CS-GY-9223-Open-Source

uv sync
uv sync --all-extras
```

The shared `chat-client-api` contract is installed from git; see the root
`pyproject.toml` `[tool.uv.sources]` section.

## Development

```bash
uv run pytest
uv run ruff check .
uv run mypy components tests
```

## Deploying to Render

This repository includes a Render Blueprint at `render.yaml` for
`chat_client_service`.

Required service-owned variables:

- `TELEGRAM_BOT_TOKEN`
- `SERVICE_BASE_URL`
- `CHAT_CLIENT_STORE_PATH`

Recommended Render values:

- `CHAT_CLIENT_STORE_PATH=/var/data/chat_client.sqlite3`
- `TELEGRAM_UPDATE_MODE=polling`
- `TELEGRAM_POLL_INTERVAL_SECONDS=3`

Optional variables:

- `APP_SESSION_SECRET` (optional signing override; defaults to the bot token)
- `APP_SESSION_TTL_SECONDS`
- `TELEGRAM_OIDC_CLIENT_ID` (optional override; otherwise derived from the bot id)
- `TELEGRAM_OIDC_CLIENT_SECRET` (optional override only for explicit code flow)
- `TELEGRAM_WEBHOOK_SECRET`
- `TELEGRAM_BOT_API_BASE_URL`

The Render blueprint in this branch also mounts a persistent disk at `/var/data`
for bot-observed messages and auth session state.

## Telegram Service Semantics

This is a bot-scoped Telegram implementation:

- sends go out through the configured bot
- reads return messages the bot observed or sent
- `channel_id="me"` means the logged-in user's direct chat with the bot
- `GET /chat/channels` returns chats known to the bot, not arbitrary Telegram dialogs

Message responses return opaque ids in `channel_id:message_id` form. Pass that
value directly to `DELETE /chat/messages/{message_id}`. If a client only has a
simple message id, it must also provide channel context.

If an example uses `OSSHWBOTTEST`, replace it with any group or channel where
the bot is present.

## Auth Flow

This branch keeps the Bot API runtime from the migration work and restores the
Telegram OIDC/session auth model from the hardened experiment branch.

Primary session-first path:

1. `POST /auth/sessions`
2. Open the returned `login_url`
3. Complete Telegram login
4. Poll `GET /auth/sessions/{session_id}` until `authenticated: true`
5. Use `X-Session-ID: <session_id>` on `/chat/*`

Login surfaces:

- `GET /auth/login?flow=page` serves the hosted Telegram Login page
- `GET /auth/login/config` returns `client_id` and `nonce` for custom frontends
- `GET /auth/login?flow=code` forces Telegram OIDC Authorization Code Flow with PKCE
- `GET /auth/callback?code=...&state=...` completes OIDC code flow
- `POST /auth/callback` completes Telegram Login library `id_token` flow
- `POST /auth/telegram-login` completes signed `tgAuthResult` browser-fragment flow

Browser clients can use the HTTP-only `chat_client_session` cookie. Manual/API
clients can use `X-Session-ID` or the returned Bearer token. Logout deletes the
cookie and session-backed `X-Session-ID`; direct Bearer tokens remain valid
until `APP_SESSION_TTL_SECONDS` expires.

Telegram documents both login paths in
[Log In With Telegram](https://core.telegram.org/bots/telegram-login). When
`TELEGRAM_OIDC_CLIENT_SECRET` is configured, the service can use the standards-
based Authorization Code + PKCE path. Without it, the hosted Telegram Login
page and Login library remain available for the same local service session
model.

## Update Delivery

Telegram delivers bot updates one way at a time:

- `TELEGRAM_UPDATE_MODE=polling` starts the background `getUpdates` poller
- `TELEGRAM_UPDATE_MODE=webhook` expects Telegram to POST to `/telegram/webhook`

For Render, the recommended path is polling plus a persistent disk. Reads remain
bot-scoped and return messages stored locally from webhook delivery, background
polling, or messages sent through the service itself.

## Project Structure

```
.
├── components/
│   ├── telegram_client_impl/              # Telegram ChatClient implementation
│   ├── chat_client_service/               # FastAPI service wrapper
│   ├── chat_client_service_api_client/    # Generated + stable service client
│   ├── chat_client_adapter/               # Adapter implementing shared ChatClient
│   ├── issue_tracker_integration/         # Team integration component
│   ├── ai_client_api/                     # Shared AI interface
│   └── openai_client_impl/                # OpenAI implementation
├── src/nyu_ospsd_chat/                    # Root Hatch wheel meta-package
├── tests/                                 # Integration / e2e tests
├── docs/                                  # MkDocs documentation
├── .circleci/                             # CircleCI CI/CD configuration
├── pyproject.toml                         # Workspace configuration
└── render.yaml                            # Render blueprint
```

## Dependency Injection Usage

```python
import telegram_client_impl
from chat_client_api import get_client

client = get_client()
```

## Documentation

```bash
uv run mkdocs serve
```

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE).
