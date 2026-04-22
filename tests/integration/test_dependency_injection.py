"""Integration tests for dependency injection between interface and implementation."""

import importlib

import chat_client_api
import chat_client_api.client as client_module
import chat_client_api.message as message_module


def test_importing_telegram_impl_injects_factories() -> None:
    """Importing telegram_client_impl registers client and message factories."""
    # Reset to baseline interface modules.
    importlib.reload(client_module)
    importlib.reload(message_module)
    importlib.reload(chat_client_api)

    original_get_message = chat_client_api.get_message

    telegram_impl = importlib.import_module("telegram_client_impl")
    importlib.reload(telegram_impl)

    injected_client = chat_client_api.get_client(interactive=False)

    assert original_get_message is not chat_client_api.get_message

    # Import here so collection does not eagerly load telegram_client_impl and
    # inject before the interface tests run. noqa: PLC0415 is intentional.
    from telegram_client_impl.client import TelegramClient  # noqa: PLC0415

    assert isinstance(injected_client, TelegramClient)
    assert chat_client_api.ChatClient is chat_client_api.Client
    assert callable(chat_client_api.register_client)
    assert callable(telegram_impl.record_update)
    assert hasattr(injected_client, "get_channel")
    assert hasattr(injected_client, "get_message")
