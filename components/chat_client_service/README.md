# Chat Client Service

FastAPI service for Telegram OIDC login and bot-scoped chat operations.

Consumers use `/auth/login` once, then call `/chat/*` with the issued Bearer token.

The service owner configures the Bot API token, BotFather Web Login Client ID,
and webhook secret. A separate app-session signing secret, custom storage paths,
and the OIDC client secret are optional deployment settings. API consumers do
not configure Telegram credentials.
