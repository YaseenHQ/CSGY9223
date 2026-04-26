# API Reference

## Interface Component: `chat_client_api`

The shared contract is defined by
[HarshithKoriRaj/Shared-API](https://github.com/HarshithKoriRaj/Shared-API).

### `ChatClient`

- `send_message(channel_id: str, text: str) -> Message`
- `get_channels() -> list[Channel]`
- `get_channel(channel_id: str) -> Channel`
- `get_messages(channel_id: str, limit: int = 10, cursor: str | None = None) -> list[Message]`
- `get_message(message_id: str) -> Message`
- `delete_message(message_id: str) -> None`

### `Message`

- `message_id: str`
- `channel: str`
- `text: str`
- `sender: str`
- `timestamp: str`

### `Channel`

- `channel_id: str`
- `name: str`
- `is_private: bool | None`
- `channel_type: str | None`

### Factory Hooks

- `get_client() -> ChatClient`
- `register_client(factory: Callable[[], ChatClient]) -> None`

## Implementation Component: `telegram_client_impl`

`telegram_client_impl` provides a Telegram-backed `ChatClient` implementation.

Importing the package performs dependency injection:

```python
import telegram_client_impl
from chat_client_api import get_client
```

The Telegram implementation uses the official Bot API. A deployed service needs
`TELEGRAM_BOT_TOKEN`, `SERVICE_BASE_URL`, and `CHAT_CLIENT_STORE_PATH`.
`get_messages` and `get_channels` read bot-observed state stored locally through
polling, webhook delivery, or service sends.

Message objects use opaque `channel_id:message_id` identifiers so clients can
pass them directly to `DELETE /chat/messages/{message_id}`.

## Service Compatibility

The shared Python API uses `limit` for message retrieval. OpenAPI clients may
send `max_results` on `GET /chat/messages`, so the FastAPI service accepts both
query parameters and forwards the effective value to
`ChatClient.get_messages(..., limit=...)`.

## Service Auth Surface

`chat_client_service` keeps the `/chat/*` contract stable and adds Telegram
login/session endpoints for HTTP consumers:

- `POST /auth/sessions`
- `GET /auth/login`
- `GET /auth/login/config`
- `GET /auth/callback`
- `POST /auth/callback`
- `POST /auth/telegram-login`
- `POST /auth/verify` (compatibility bridge)
- `GET /auth/sessions/{session_id}`
- `DELETE /auth/sessions/{session_id}`
- `GET /auth/me`

The preferred adapter/client flow is `POST /auth/sessions` followed by
`X-Session-ID` on `/chat/*`. Direct Bearer tokens are still accepted.
## Components

Documentation for chat client components will be added here as the implementation develops.
