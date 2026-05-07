"""Configuration primitives for Telegram client setup."""

from dataclasses import dataclass
from os import getenv


@dataclass(frozen=True)
class TelegramClientConfig:
    """Configuration required to initialize a Telegram Bot API client."""

    bot_token: str | None
    bot_api_base_url: str = "https://api.telegram.org"
    interactive: bool = False

    @classmethod
    def from_env(cls, *, interactive: bool = False) -> "TelegramClientConfig":
        """Create config from environment variables only."""
        return cls(
            bot_token=getenv("TELEGRAM_BOT_TOKEN"),
            bot_api_base_url=getenv(
                "TELEGRAM_BOT_API_BASE_URL",
                "https://api.telegram.org",
            ),
            interactive=interactive,
        )
