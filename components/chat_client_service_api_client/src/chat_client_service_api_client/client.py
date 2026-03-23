"""Stable wrapper over generated OpenAPI client implementation."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from chat_client_service_api_client.models import ChannelDTO, MessageDTO


class ChatServiceApiClient:
    """Small abstraction layer over generated service client code.

    The generated package can be replaced/regenerated without forcing import-path
    changes for consumers such as the adapter.
    """

    def __init__(self, *, base_url: str) -> None:
        """Initialize client wrapper with service base URL."""
        self._base_url = base_url.rstrip("/")

    @property
    def base_url(self) -> str:
        """Return normalized base URL."""
        return self._base_url

    def send_message(self, *, channel_id: str, text: str) -> MessageDTO:
        """Send message through service API."""
        _ = (channel_id, text)
        msg = "Wire to generated client send_message endpoint."
        raise NotImplementedError(msg)

    def get_messages(
        self,
        *,
        channel_id: str,
        max_results: int = 10,
    ) -> list[MessageDTO]:
        """Fetch messages through service API."""
        _ = (channel_id, max_results)
        msg = "Wire to generated client get_messages endpoint."
        raise NotImplementedError(msg)

    def delete_message(self, *, channel_id: str, message_id: str) -> bool:
        """Delete message through service API."""
        _ = (channel_id, message_id)
        msg = "Wire to generated client delete_message endpoint."
        raise NotImplementedError(msg)

    def get_channels(self) -> list[ChannelDTO]:
        """Fetch channels through service API."""
        msg = "Wire to generated client get_channels endpoint."
        raise NotImplementedError(msg)
