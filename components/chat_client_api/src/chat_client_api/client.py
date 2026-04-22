"""Core chat client contract definitions and injectable factory hook."""

from abc import ABC, abstractmethod
from collections.abc import Callable

from chat_client_api.channel import Channel
from chat_client_api.message import Message


class Client(ABC):
    """Abstract base class representing a chat client."""

    @abstractmethod
    def send_message(self, channel_id: str, text: str) -> Message:
        """Send a message to a channel.

        Args:
            channel_id: The target channel or conversation ID.
            text: The message content to send.

        Returns:
            The sent Message object.

        """
        raise NotImplementedError

    @abstractmethod
    def get_channels(self) -> list[Channel]:
        """Return available channels or conversations.

        Returns:
            Channel objects.

        """
        raise NotImplementedError

    @abstractmethod
    def get_channel(self, channel_id: str) -> Channel:
        """Return one channel by ID.

        Args:
            channel_id: Channel or conversation ID.

        Returns:
            Channel object.

        Raises:
            ValueError: If the channel is not known.

        """
        raise NotImplementedError

    @abstractmethod
    def get_messages(
        self,
        channel_id: str,
        limit: int = 10,
        cursor: str | None = None,
    ) -> list[Message]:
        """Return messages from a channel.

        Args:
            channel_id: The channel or conversation to fetch messages from.
            limit: Maximum number of messages to return.
            cursor: Optional pagination cursor. Implementations may ignore it.

        Returns:
            Message objects. Results are not paginated; at most the requested
            number of messages are returned.

        """
        raise NotImplementedError

    @abstractmethod
    def get_message(self, message_id: str) -> Message:
        """Return one message by its opaque ID.

        Args:
            message_id: Message ID, or ``channel_id:message_id``.

        Returns:
            Message object.

        Raises:
            ValueError: If the message is not known.

        """
        raise NotImplementedError

    @abstractmethod
    def delete_message(self, message_id: str) -> None:
        """Delete a message by its ID.

        Args:
            message_id: Opaque ``channel_id:message_id`` identifier.

        Raises:
            MessageNotFoundError: If the message does not exist.
            PermissionError: If the client lacks permission to delete.

        """
        raise NotImplementedError


ChatClient = Client


class _ClientRegistry:
    """Registry for shared-API style client factory injection."""

    _factory: Callable[[], Client] | None = None

    @classmethod
    def set(cls, factory: Callable[[], Client]) -> None:
        """Register a client factory."""
        cls._factory = factory

    @classmethod
    def get(cls) -> Callable[[], Client] | None:
        """Return the registered client factory, if any."""
        return cls._factory


def get_client(*, interactive: bool = False) -> Client:
    """Return an instance of a Chat Client.

    Args:
        interactive: If True, allow interactive authentication prompts.

    Returns:
        A Client instance.

    Raises:
        NotImplementedError: If no implementation has been injected.

    """
    del interactive
    factory = _ClientRegistry.get()
    if factory is not None:
        return factory()
    raise NotImplementedError


def register_client(factory: Callable[[], Client]) -> None:
    """Register a concrete chat client factory."""
    _ClientRegistry.set(factory)
