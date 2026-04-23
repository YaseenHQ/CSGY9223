# Telegram Implementation

## Package Layout

- `components/telegram_client_impl/pyproject.toml`
- `components/telegram_client_impl/README.md`
- `components/telegram_client_impl/src/telegram_client_impl/*.py`

## Injection Behavior

When `telegram_client_impl` is imported, it registers implementation factories into
`chat_client_api`:

- `chat_client_api.get_client`
- `chat_client_api.get_message`

This allows consumers to code against the interface while swapping implementation
by import.

## Authentication and Runtime Mode

Configuration is read from environment variables:

- `TELEGRAM_API_ID`
- `TELEGRAM_API_HASH`
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_SESSION_NAME`
- `TELEGRAM_SESSION_STRING`

No credentials are hardcoded.

`TELEGRAM_SESSION_STRING` should be preferred in deployed service environments.
Telethon session files are local SQLite files; Render and other ephemeral hosts
should use a string session instead of relying on a file created in the working
directory.

## Bot Token vs User Session

Telegram bot auth is not equivalent to a user session:

| Credential | Works for | Does not reliably work for |
|---|---|---|
| Bot token | Login Widget HMAC verification; sending messages where the bot has access | Reading arbitrary history with `GetHistoryRequest`; listing user dialogs with `GetDialogsRequest` |
| User session string | Sending messages, reading message history, listing dialogs visible to that user | Login Widget HMAC verification |

The deployed service needs both credentials: bot token for web login/Bearer
signing, user session string for the Telegram chat backend. Bot fallback is
restricted to send operations; read/list requires a user session.

## Chat Targets

Use `channel_id="me"` for Saved Messages only. For any group/channel usage,
first list dialogs with `get_channels()` or the service's `GET /chat/channels`,
then use the returned `Channel.channel_id`.

This example uses `OSSHWBOTTEST`; replace it with any group or channel of your
choice:

```python
import telegram_client_impl
from chat_client_api import get_client

client = get_client()
target = next(ch for ch in client.get_channels() if ch.name == "OSSHWBOTTEST")

client.send_message(channel_id=target.channel_id, text="hello group")
latest = client.get_messages(channel_id=target.channel_id, limit=1)[0]
print(latest.text)
```

If a target group does not appear in `get_channels()`, the Telegram user behind
`TELEGRAM_SESSION_STRING` has not joined it, the session is invalid, or the
service is running in bot-token-only mode.

## Generating a User Session String

Use the Telegram API ID/hash from [Telegram API development tools](https://core.telegram.org/api/obtaining_api_id),
then generate a Telethon string session using the account that should read/send
messages. Telethon documents this flow under [String Sessions](https://docs.telethon.dev/en/stable/concepts/sessions.html#string-sessions).

```python
from telethon.sync import TelegramClient
from telethon.sessions import StringSession

api_id = int(input("api_id: "))
api_hash = input("api_hash: ")

with TelegramClient(StringSession(), api_id, api_hash) as client:
    print(client.session.save())
```

Paste the complete output into Render as `TELEGRAM_SESSION_STRING`. Do not paste
a screenshot preview; the value is long and must not be truncated.
