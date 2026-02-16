"""E2E wiring test for Telegram client scaffold.

This test is env-gated because real provider credentials are external.
"""

import importlib
from os import getenv

import pytest


@pytest.mark.e2e
def test_telegram_wiring_e2e() -> None:
    """Validate interface -> implementation wiring in an E2E-style path."""
    if getenv("TELEGRAM_E2E_ENABLED") != "1":
        pytest.skip("Set TELEGRAM_E2E_ENABLED=1 to run Telegram E2E scaffold test")

    importlib.import_module("telegram_client_impl")
    get_client = importlib.import_module("chat_client_api").get_client

    client = get_client(interactive=False)

    with pytest.raises(NotImplementedError):
        list(client.get_channels())
