# API Reference

## Interface Component: `chat_client_api`

### `Client`

- `send_message(channel_id: str, text: str) -> Message`
- `get_channels() -> list[Channel]`
- `get_channel(channel_id: str) -> Channel`
- `get_messages(channel_id: str, limit: int = 10, cursor: str | None = None) -> list[Message]`
- `get_message(message_id: str) -> Message`
- `delete_message(message_id: str) -> None`

`ChatClient` is exported as an alias for `Client`, and `register_client()` is
available for compatibility with the shared chat API package.

### `Message`

- `id: str`
- `message_id: str` alias for `id`
- `sender: str`
- `channel_id: str`
- `channel: str` alias for `channel_id`
- `timestamp: str`
- `text: str`

### `Channel`

- `id: str`
- `channel_id: str` alias for `id`
- `name: str`
- `channel_type: str`
- `is_private: bool | None`

### Factory Hooks

- `get_client(*, interactive: bool = False) -> Client`
- `get_message(msg_id: str, raw_data: str) -> Message`

## Implementation Component: `telegram_client_impl`

`telegram_client_impl` provides Bot API implementations for:

- `TelegramClient`
- `TelegramMessage`
- `TelegramChannel`

Importing the package performs dependency injection:

```python
import telegram_client_impl
from chat_client_api import get_client
```

The implementation uses the official Telegram Bot API. Reads and channel lists
are bot-scoped: they return messages and chats observed by the bot or sent
through this service.

## Service Component: `chat_client_service`

- `GET /health`
- `GET /auth/login`
- `GET /auth/login/config`
- `GET /auth/callback`
- `POST /auth/callback`
- `GET /auth/me`
- `GET /chat/channels`
- `POST /chat/messages`
- `GET /chat/messages`
- `DELETE /chat/messages/{message_id}`
- `POST /telegram/webhook`

All `/chat/*` routes require `Authorization: Bearer <token>` from `/auth/login`.
Use `channel_id=me` for the logged-in user's direct chat with the bot, or a
Telegram chat ID for a group/channel where the bot is present and has observed
that user through webhook updates or can verify membership with Bot API
`getChatMember`.
Message `id` values returned by the HTTP API are opaque
`channel_id:message_id` strings that can be passed directly to
`DELETE /chat/messages/{message_id}`.
