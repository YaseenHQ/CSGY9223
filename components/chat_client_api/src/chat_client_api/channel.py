"""Channel contract - Core channel representation for chat clients."""

from abc import ABC, abstractmethod


class Channel(ABC):
    """Abstract base class representing a chat channel or conversation."""

    @property
    @abstractmethod
    def id(self) -> str:
        """Return the unique identifier of the channel."""
        raise NotImplementedError

    @property
    def channel_id(self) -> str:
        """Return the shared-API channel identifier alias."""
        return self.id

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the display name of the channel."""
        raise NotImplementedError

    @property
    @abstractmethod
    def channel_type(self) -> str:
        """Return the type of channel (e.g. 'group', 'private', 'channel')."""
        raise NotImplementedError

    @property
    def is_private(self) -> bool | None:
        """Return whether the channel is private when known."""
        return None
