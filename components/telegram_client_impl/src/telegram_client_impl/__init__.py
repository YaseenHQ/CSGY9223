"""Register Telegram factory functions with ``chat_client_api``."""

from importlib import import_module
from types import ModuleType
from typing import Any, cast

import chat_client_api
from telegram_client_impl.client import get_client_impl
from telegram_client_impl.message import get_message_impl
from telegram_client_impl.store import record_update as record_update

chat_client_api.register_client(lambda: get_client_impl(interactive=False))
cast("Any", chat_client_api).get_message = get_message_impl

try:
    message_module: ModuleType | None = import_module("chat_client_api.message")
except ImportError:
    message_module = None

if message_module is not None:
    cast("Any", message_module).get_message = get_message_impl
