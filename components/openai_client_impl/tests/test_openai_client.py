"""Unit tests for :class:`openai_client_impl.OpenAIClient`."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest
from openai import OpenAI

from openai_client_impl import OpenAIClient
from openai_client_impl.config import OpenAIClientConfig
from openai_client_impl.errors import OpenAIClientError


def _mock_completion(content: str | None) -> MagicMock:
    response = MagicMock()
    message = MagicMock()
    message.content = content
    message.tool_calls = None
    choice = MagicMock()
    choice.message = message
    response.choices = [choice]
    return response


def test_send_message_delegates_to_openai_sdk() -> None:
    """``send_message`` calls chat completions and returns assistant text."""
    mock_sdk = MagicMock(spec=OpenAI)
    mock_sdk.chat.completions.create.return_value = _mock_completion("ok")

    client = OpenAIClient(
        config=OpenAIClientConfig(api_key="sk-test", model="gpt-test"),
        client=mock_sdk,
    )
    result = client.send_message("ping")

    assert result == "ok"
    mock_sdk.chat.completions.create.assert_called_once()
    call_kw = mock_sdk.chat.completions.create.call_args.kwargs
    assert call_kw["model"] == "gpt-test"
    assert len(call_kw["messages"]) == 1
    assert call_kw["messages"][0]["role"] == "user"
    assert "ping" in call_kw["messages"][0]["content"]


def test_send_message_passes_tools_to_openai_sdk() -> None:
    """Optional ``tools`` are forwarded to chat completions."""
    mock_sdk = MagicMock(spec=OpenAI)
    mock_sdk.chat.completions.create.return_value = _mock_completion("ok")

    client = OpenAIClient(
        config=OpenAIClientConfig(api_key="sk-test", model="gpt-test"),
        client=mock_sdk,
    )
    tools = [
        {
            "type": "function",
            "function": {
                "name": "get_weather",
                "description": "Get weather by city.",
                "parameters": {
                    "type": "object",
                    "properties": {"city": {"type": "string"}},
                    "required": ["city"],
                },
            },
        }
    ]
    client.send_message("weather?", tools=tools)

    call_kw = mock_sdk.chat.completions.create.call_args.kwargs
    assert call_kw["tools"] == tools


def test_send_message_includes_context_in_user_content() -> None:
    """Optional ``context`` is embedded in the user message."""
    mock_sdk = MagicMock(spec=OpenAI)
    mock_sdk.chat.completions.create.return_value = _mock_completion("done")

    client = OpenAIClient(
        config=OpenAIClientConfig(api_key="sk-test", model="gpt-test"),
        client=mock_sdk,
    )
    ctx: dict[str, Any] = {"k": 1}
    client.send_message("go", context=ctx)

    content = mock_sdk.chat.completions.create.call_args.kwargs["messages"][0][
        "content"
    ]
    assert "Context (JSON):" in content
    assert '"k":1' in content
    assert "go" in content


def test_missing_api_key_raises() -> None:
    """Constructing without SDK client or API key fails fast."""
    with pytest.raises(OpenAIClientError, match="OPENAI_API_KEY"):
        OpenAIClient(config=OpenAIClientConfig(api_key="", model="gpt-test"))


def test_empty_model_response_raises() -> None:
    """Null assistant content surfaces as ``OpenAIClientError``."""
    mock_sdk = MagicMock(spec=OpenAI)
    mock_sdk.chat.completions.create.return_value = _mock_completion(None)

    client = OpenAIClient(
        config=OpenAIClientConfig(api_key="sk-test", model="gpt-test"),
        client=mock_sdk,
    )
    with pytest.raises(OpenAIClientError, match="empty content"):
        client.send_message("hi")


def test_tool_call_returns_structured_response() -> None:
    """Tool calls return function name and parsed JSON arguments."""
    mock_sdk = MagicMock(spec=OpenAI)
    completion = _mock_completion(None)
    tool_call = MagicMock()
    tool_call.function.name = "get_weather"
    tool_call.function.arguments = '{"city":"NYC"}'
    completion.choices[0].message.tool_calls = [tool_call]
    mock_sdk.chat.completions.create.return_value = completion

    client = OpenAIClient(
        config=OpenAIClientConfig(api_key="sk-test", model="gpt-test"),
        client=mock_sdk,
    )
    result = client.send_message("weather?")
    assert result == {"name": "get_weather", "arguments": {"city": "NYC"}}


def test_tool_call_invalid_json_raises() -> None:
    """Invalid tool-call JSON arguments raise ``OpenAIClientError``."""
    mock_sdk = MagicMock(spec=OpenAI)
    completion = _mock_completion(None)
    tool_call = MagicMock()
    tool_call.function.name = "get_weather"
    tool_call.function.arguments = "{bad json"
    completion.choices[0].message.tool_calls = [tool_call]
    mock_sdk.chat.completions.create.return_value = completion

    client = OpenAIClient(
        config=OpenAIClientConfig(api_key="sk-test", model="gpt-test"),
        client=mock_sdk,
    )
    with pytest.raises(OpenAIClientError, match="invalid JSON"):
        client.send_message("weather?")
