# Chat Client Service

FastAPI service for Telegram OIDC login and bot-scoped chat operations.

Consumers create `/auth/sessions`, complete Telegram login, then call `/chat/*`
with `X-Session-ID`. Direct Bearer tokens from `/auth/callback` are also
accepted for compatibility.

The service owner configures the Bot API token, BotFather Web Login Client ID,
service base URL, webhook secret, app-session signing secret, and storage path.
The OIDC client secret is only needed for `GET /auth/login?flow=code`; the
default service-hosted login page does not use it. API consumers do not
configure Telegram credentials.
