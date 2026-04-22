# CS-GY-9223 Open Source

A plug-and-play Telegram chat API using Telegram OpenID Connect for login and
the official Bot API for bot-scoped chat operations.

## Team

**Team name:** Team 4

**Members:**

- Yukta Kulkarni — yk3213 (yuktakul04)
- Sumanth Subramanian Ramesh — sr7420
- Karthik Subramanian — ks7886
- Pranav Raj N K — pn2330
- Mohamed Yaseen Mohamed Shuaib — mm14451

**Course staff (collaborators to add):**

- adithyab-20
- ivanearisty
- AranyaAryaman

## Prerequisites

- Python 3.10 or higher
- [uv](https://docs.astral.sh/uv/) package manager

## Installation

```bash
# Clone the fork used for this Bot API/OIDC experiment
git clone https://github.com/YaseenHQ/CSGY9223.git
cd CSGY9223

# Install dependencies
uv sync

# Install with all dependencies (dev + docs)
uv sync --all-extras
```

## Development

```bash
# Run tests
uv run pytest

# Run linting
uv run ruff check .

# Run type checking
uv run mypy components tests
```

## API Usage

API consumers do not configure Telegram credentials. They create an auth session,
complete Telegram login, then call `/chat/*` with `X-Session-ID`. Direct Bearer
tokens from `/auth/callback` are still accepted for compatibility.

## Service Configuration

For Render, the shared service needs one service-owned bot. API users do not set
Telegram credentials; they only log in through `/auth/*`.

| Variable | Purpose |
| --- | --- |
| `TELEGRAM_BOT_TOKEN` | Bot token from [@BotFather](https://t.me/BotFather), used for Bot API send/delete/webhook calls. |
| `SERVICE_BASE_URL` | Render URL, e.g. `https://your-service.onrender.com`; used for login URLs and webhook setup. |
| `TELEGRAM_WEBHOOK_SECRET` | Random webhook secret checked on `/telegram/webhook`. |
| `CHAT_CLIENT_STORE_PATH` | SQLite store path. Use `/var/data/chat_client.sqlite3` on Render. |

Optional deployment settings:

| Variable | Default | Purpose |
| --- | --- | --- |
| `APP_SESSION_SECRET` | `TELEGRAM_BOT_TOKEN` | Override for signing local API sessions. |
| `APP_SESSION_TTL_SECONDS` | `3600` | Local Bearer token lifetime. |
| `TELEGRAM_OIDC_CLIENT_ID` | bot token numeric prefix | Override only if BotFather displays a separate Web Login Client ID. |
| `TELEGRAM_OIDC_CLIENT_SECRET` | unset | Required only for `GET /auth/login?flow=code`. The default login page does not use it. |
| `TELEGRAM_WEBHOOK_ALLOWED_UPDATES` | `message,edited_message,channel_post,edited_channel_post,my_chat_member` | Comma-separated Bot API update types for webhook setup. |
| `TELEGRAM_WEBHOOK_DROP_PENDING_UPDATES` | unset | Set to `true` to discard pending updates while configuring the webhook. |
| `TELEGRAM_BOT_API_BASE_URL` | `https://api.telegram.org` | Override only for a custom Bot API server. |

Telegram documents the Login library and OIDC setup in
[Log In With Telegram](https://core.telegram.org/bots/telegram-login).
The current page says the legacy iframe-based widget docs are archived; this
project uses the current `Telegram.Login` library and OIDC ID-token validation.
In BotFather Web Login settings, register the Render service origin
(`https://your-service.onrender.com`). Register
`${SERVICE_BASE_URL}/auth/callback` only if you enable `?flow=code`.
If BotFather does not show a separate Client ID, leave
`TELEGRAM_OIDC_CLIENT_ID` unset; the service uses the numeric bot id from the
bot token as the Telegram Login client id.

Primary session-first login path:

1. Call `POST /auth/sessions`.
2. Open the returned `login_url`.
3. Complete Telegram login in the service-hosted page.
4. Poll `GET /auth/sessions/{session_id}` until `authenticated: true`.
5. Use `X-Session-ID: <session_id>` on `/chat/*`.

Custom frontends can instead call `GET /auth/login/config?session_id=...`, pass
`client_id` and `nonce` to `Telegram.Login.init(...)`, then send Telegram's
callback `id_token` and the same `nonce` to
   `POST /auth/callback`.

Manual clients may also use the returned Bearer token directly on `/chat/*`.

OIDC-compatible clients can use `GET /auth/login?flow=code`, which performs
Authorization Code Flow with PKCE and requires `TELEGRAM_OIDC_CLIENT_SECRET`.

Chat endpoints are bot-scoped: sends/deletes use the official Bot API, and reads
return messages the bot observed through webhooks or sent through the service.
Message responses return opaque ids in `channel_id:message_id` form; pass that
id to `DELETE /chat/messages/{message_id}`.
If a user has no cached chat grant yet, the service verifies membership with
Bot API `getChatMember` before allowing `/chat/*` access. Telegram only
guarantees `getChatMember` for other users when the bot is an administrator in
that chat.

After deploy, configure Telegram to send updates to the service:

```bash
export TELEGRAM_BOT_TOKEN=...
export SERVICE_BASE_URL=https://your-service.example
export TELEGRAM_WEBHOOK_SECRET=...
uv run python scripts/configure_telegram_webhook.py
```

For group reads, add the bot to the chat and make sure the webhook is configured
so Telegram delivers new messages to `/telegram/webhook`. Replace
`OSSHWBOTTEST` in examples with any group, channel, or DM where the bot is
present. `me` means the logged-in user's direct chat with the bot.
The webhook rejects requests unless `TELEGRAM_WEBHOOK_SECRET` is set and Telegram
sends the matching secret header.
Telegram keeps undelivered updates for at most 24 hours, and `getUpdates` cannot
be used while a webhook is configured.

## Documentation

```bash
uv run mkdocs serve
```

## Project Structure

```
.
├── components/      # Interface + implementation components
│   ├── chat_client_api/         # chat_client_api interface component
│   ├── chat_client_service/     # FastAPI OIDC + chat service
│   └── telegram_client_impl/    # Telegram Bot API implementation component
├── tests/           # Test suite
├── docs/            # MkDocs documentation
├── .circleci/       # CircleCI CI/CD configuration
├── pyproject.toml   # Project configuration
└── README.md
```

## Dependency Injection Usage

```python
import telegram_client_impl  # injects factory hooks into chat_client_api
from chat_client_api import get_client

client = get_client(interactive=False)
```

## License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.
