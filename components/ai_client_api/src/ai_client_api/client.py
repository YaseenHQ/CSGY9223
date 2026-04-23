"""Abstract base class for AI client implementations."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, TypedDict


class ToolCallResponse(TypedDict):
    """Structured tool invocation returned by an LLM response."""

    name: str
    arguments: dict[str, Any]


class AIClient(ABC):
    """Protocol for LLM-backed text generation."""

    @abstractmethod
    def send_message(
        self,
        prompt: str,
        context: dict[str, Any] | None = None,
        tools: list[dict[str, Any]] | None = None,
    ) -> str | ToolCallResponse:
        """Return model text or a structured tool call for ``prompt``."""
