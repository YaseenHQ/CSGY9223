"""Abstract base class for AI client implementations."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, TypedDict


class _ToolCallResponseRequired(TypedDict):
    name: str
    arguments: dict[str, Any]


class ToolCallResponse(_ToolCallResponseRequired, total=False):
    """Structured tool invocation returned by an LLM response.

    ``name`` and ``arguments`` are always present.  ``output`` is optional
    and may be populated after the tool has been executed with its result.
    """

    output: str | None


class AIClient(ABC):
    """Protocol for LLM-backed text generation."""

    @abstractmethod
    def send_message(
        self,
        prompt: str,
        context: dict[str, Any] | None = None,
        tools: list[dict[str, Any]] | None = None,
    ) -> str | ToolCallResponse:
        """Process ``prompt`` and return the model's response.

        Returns a plain ``str`` for text-only responses, or a
        ``ToolCallResponse`` dict when the model invokes a tool.  The
        ``ToolCallResponse`` includes the tool ``name``, its ``arguments``,
        and optionally an ``output`` field populated after the tool has been
        executed and its result recorded.
        """
