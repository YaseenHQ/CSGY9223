"""Integration tests for dependency injection through chat_client_adapter."""

import importlib

import chat_client_api
import chat_client_api.client as client_module


def test_importing_adapter_injects_get_client_factory() -> None:
    """Importing chat_client_adapter rebinds chat_client_api.get_client."""
    importlib.reload(client_module)
    importlib.reload(chat_client_api)

    original_get_client = chat_client_api.get_client

    adapter_module = importlib.import_module("chat_client_adapter")
    importlib.reload(adapter_module)

    assert original_get_client is not chat_client_api.get_client

    from chat_client_adapter.client import ServiceBackedChatClient  # noqa: PLC0415

    injected_client = chat_client_api.get_client(interactive=False)
    assert isinstance(injected_client, ServiceBackedChatClient)
