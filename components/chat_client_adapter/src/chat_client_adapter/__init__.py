"""Inject adapter client factory into ``chat_client_api``."""

import chat_client_api
import chat_client_api.client as client_module
from chat_client_adapter.client import get_client_impl

client_module.get_client = get_client_impl
chat_client_api.get_client = get_client_impl
