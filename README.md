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

## Project Structure

```
.
├── components/
│   └── telegram_client_impl/   # Telegram ChatClient implementation
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

- `TELEGRAM_API_ID`, `TELEGRAM_API_HASH`, `TELEGRAM_BOT_TOKEN` — required for a live client
- `TELEGRAM_SESSION_NAME` — optional session file basename
- `TELEGRAM_INTERACTIVE` — set to `1` / `true` / `yes` if you use interactive-oriented
  config (factory reads env only; there is no `get_client(interactive=...)` on the shared API)

## License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.
