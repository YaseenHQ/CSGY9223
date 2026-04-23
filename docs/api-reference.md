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

The Telegram implementation uses Telethon. A deployed service needs a valid
`TELEGRAM_SESSION_STRING` for read/list operations; bot-token-only mode can send
in some chats but does not support the history/dialog APIs used by
`get_messages` and `get_channels`.

## Service Compatibility

The shared Python API uses `limit` for message retrieval. The generated service
client previously used `max_results` on `GET /chat/messages`, so the FastAPI
service accepts both query parameters and forwards the effective value to
`ChatClient.get_messages(..., limit=...)`.
## Components

Documentation for chat client components will be added here as the implementation develops.
