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

API consumers do not configure Telegram credentials. They open `/auth/login`,
complete Telegram login, and call `/chat/*` with the issued Bearer token.

## Service Configuration

For the default Telegram Login library path, the shared service needs its
service-owned bot token and BotFather Web Login Client ID. API users do not set
any of these values.

| Variable | Purpose |
| --- | --- |
| `TELEGRAM_BOT_TOKEN` | Bot token from [@BotFather](https://t.me/BotFather), used for Bot API send/delete/webhook calls. |
| `TELEGRAM_OIDC_CLIENT_ID` | Web Login Client ID from BotFather, passed to `Telegram.Login.init(...)` and used as the ID-token audience. |

Optional deployment settings:

| Variable | Default | Purpose |
| --- | --- | --- |
| `APP_SESSION_SECRET` | `TELEGRAM_BOT_TOKEN` | Override for signing local Bearer tokens. Recommended for production rotation separation. |
| `TELEGRAM_OIDC_CLIENT_SECRET` | unset | Required only for the OIDC Authorization Code Flow at `GET /auth/login`. The Telegram Login JS library path does not use it. |
| `SERVICE_BASE_URL` | `http://localhost:8000` | Required for redirect flow and webhook setup; register `${SERVICE_BASE_URL}/auth/callback` in BotFather Web Login allowed URLs. |
| `APP_SESSION_TTL_SECONDS` | `3600` | Local Bearer token lifetime. |
| `CHAT_CLIENT_STORE_PATH` | `.data/chat_client.sqlite3` | SQLite store path. Use `/var/data/chat_client.sqlite3` on Render. |
| `TELEGRAM_WEBHOOK_SECRET` | unset | Required for webhook setup and checked on `/telegram/webhook`. |
| `TELEGRAM_WEBHOOK_ALLOWED_UPDATES` | `message,edited_message,channel_post,edited_channel_post,my_chat_member` | Comma-separated Bot API update types for webhook setup. |
| `TELEGRAM_WEBHOOK_DROP_PENDING_UPDATES` | unset | Set to `true` to discard pending updates while configuring the webhook. |
| `TELEGRAM_BOT_API_BASE_URL` | `https://api.telegram.org` | Override only for a custom Bot API server. |

Telegram documents the Login library and OIDC setup in
[Log In With Telegram](https://core.telegram.org/bots/telegram-login).
The current page says the legacy iframe-based widget docs are archived; this
project uses the current `Telegram.Login` library and OIDC ID-token validation.

Primary login path for custom frontends:

1. Call `GET /auth/login/config`.
2. Pass `client_id` and `nonce` to `Telegram.Login.init(...)`.
3. Send Telegram's callback `id_token` and the same `nonce` to
   `POST /auth/callback`.
4. Use the returned Bearer token on `/chat/*`.

OIDC-compatible clients can instead use `GET /auth/login`, which performs
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
export TELEGRAM_OIDC_CLIENT_ID=...
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
