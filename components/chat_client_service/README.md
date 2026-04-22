# Chat Client Service

FastAPI service for Telegram OIDC login and bot-scoped chat operations.

Consumers create `/auth/sessions`, complete Telegram login, then call `/chat/*`
with `X-Session-ID`. Direct Bearer tokens from `/auth/callback` are also
accepted for compatibility.

The service owner configures the Bot API token, service base URL, webhook
secret, and storage path. The service derives the Telegram Login client id and
default app-session signing secret from the bot token unless explicit overrides
are set. API consumers do not configure Telegram credentials.
