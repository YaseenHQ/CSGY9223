# CS-GY-9223 Open Source

A chat client workspace with a **shared vertical API** (git dependency) and a **Telegram** implementation.

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

- Python 3.12 or higher (required by the shared `chat-client-api` package)
- [uv](https://docs.astral.sh/uv/) package manager

## Installation

```bash
# Clone the repository
git clone https://github.com/yuktakul04/CS-GY-9223-Open-Source.git
cd CS-GY-9223-Open-Source

# Install dependencies
uv sync

# Install with all dependencies (dev + docs)
uv sync --all-extras
```

The shared contract is installed from git, for example:

`chat-client-api` ← [HarshithKoriRaj/Shared-API](https://github.com/HarshithKoriRaj/Shared-API) (see root `pyproject.toml` `[tool.uv.sources]`).

## Development

```bash
# Run tests
uv run pytest

# Run linting
uv run ruff check .

# Run type checking
uv run mypy components tests
```

## Documentation

```bash
uv run mkdocs serve
```

## Deploying to Render

This repository includes a Render Blueprint at `render.yaml` for
`chat_client_service`.

1. In Render, create a new Blueprint service from this repo.
2. Set required environment variables:
   - `TELEGRAM_API_ID`
   - `TELEGRAM_API_HASH`
   - `TELEGRAM_BOT_TOKEN`
   - `TELEGRAM_SESSION_STRING`
   - `SERVICE_BASE_URL` (for example `https://<your-service>.onrender.com`)
3. Deploy and verify:
   - `GET /health` returns `{"status":"ok"}`
   - `GET /auth/login` redirects to Telegram OAuth

`TELEGRAM_BOT_TOKEN` is not enough for the full chat API. It is used for Telegram
Login Widget verification and this service's Bearer-token signing. `GET
/chat/messages` and `GET /chat/channels` require a Telethon user session string
generated from a Telegram user account that can see the target chat.

Credential sources:

- `TELEGRAM_BOT_TOKEN`: create a bot with [BotFather](https://t.me/BotFather).
- `TELEGRAM_API_ID` and `TELEGRAM_API_HASH`: create an app in [Telegram API development tools](https://core.telegram.org/api/obtaining_api_id).
- `TELEGRAM_SESSION_STRING`: generate a [Telethon String Session](https://docs.telethon.dev/en/stable/concepts/sessions.html#string-sessions) from the Telegram user account used for read/list/send operations.

Do not commit `.env`, `*.session`, bot tokens, API hashes, or session strings.
Treat `TELEGRAM_SESSION_STRING` like an account password.

## Project Structure

```
.
├── components/
│   ├── telegram_client_impl/              # Telegram ChatClient implementation
│   ├── chat_client_service/               # FastAPI service wrapper
│   ├── chat_client_service_api_client/    # Generated + stable service client
│   └── chat_client_adapter/               # Adapter implementing shared ChatClient
├── src/nyu_ospsd_chat/         # Root Hatch wheel meta-package
├── tests/                      # Integration / e2e tests
├── docs/                       # MkDocs documentation
├── .circleci/                  # CircleCI CI/CD configuration
├── pyproject.toml              # Project configuration
└── README.md
```

## Dependency injection usage

```python
import telegram_client_impl  # registers the Telegram factory via register_client
from chat_client_api import get_client

client = get_client()
```

### Opaque Telegram `message_id`

Outbound `Message.message_id` values use `<chat_id>:<telegram_message_id>`. Parse with
`split(":", 1)`. Invalid or missing messages raise `ValueError` where the shared API
specifies it.

### Environment

- `TELEGRAM_API_ID`, `TELEGRAM_API_HASH` — required for a live Telethon client
- `TELEGRAM_BOT_TOKEN` — required for service login/Bearer signing; send-only fallback
- `TELEGRAM_SESSION_STRING` — required for deployed read/list and preferred for send
- `TELEGRAM_SESSION_NAME` — optional session file basename
- `TELEGRAM_INTERACTIVE` — set to `1` / `true` / `yes` if you use interactive-oriented
  config (factory reads env only; there is no `get_client(interactive=...)` on the shared API)

Use `channel_id="me"` only for the Telegram user's Saved Messages. To send/read
any real group or channel, call `GET /chat/channels` with a valid Bearer token,
find the target by `name`, and pass that returned `id` as `channel_id`.
If an example uses `OSSHWBOTTEST`, replace it with any group or channel of your
choice.

## License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.
