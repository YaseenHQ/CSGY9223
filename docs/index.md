# Chat Client

Welcome to the Chat Client documentation.

## Overview

This project provides an interface, Telegram Bot API implementation, and hosted
FastAPI service for a chat client.

- `chat_client_api`: a provider-agnostic chat interface contract
- `telegram_client_impl`: a Telegram Bot API implementation injected via factory hooks
- `chat_client_service`: Telegram OIDC login plus protected `/chat/*` routes

## Quick Links

- [Getting Started](getting-started.md)
- [API Reference](api-reference.md)
- [Telegram Implementation](telegram-implementation.md)
