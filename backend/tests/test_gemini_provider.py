
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.services.gemini_provider import GeminiProvider


@pytest.fixture
def provider():
    instance = GeminiProvider.__new__(GeminiProvider)
    instance.model = "gemini-3.8-flash"
    instance.client = MagicMock()
    return instance


@pytest.mark.parametrize(
    ("finish_reason", "expected"),
    [
        ("STOP", True),
        ("FinishReason.STOP", True),
        ("MAX_TOKENS", False),
        ("SAFETY", False),
        ("UNKNOWN", False),
    ],
)
def test_finish_reason_detection(provider, finish_reason, expected):
    response = SimpleNamespace(
        usage_metadata=SimpleNamespace(
            prompt_token_count=100,
            candidates_token_count=50,
            thoughts_token_count=0,
            tool_use_prompt_token_count=0,
        ),
        candidates=[
            SimpleNamespace(finish_reason=finish_reason)
        ],
        text="Test documentation",
    )

    provider.client.models.generate_content.return_value = response

    result = provider.generate("Test prompt")

    assert result["is_complete"] is expected
    assert result["finish_reason"] == finish_reason
    assert result["content"] == "Test documentation"
    assert result["total_tokens"] == 150


def test_empty_prompt_does_not_call_gemini(provider):
    with pytest.raises(ValueError, match="Prompt cannot be empty"):
        provider.generate(" ")

    provider.client.models.generate_content.assert_not_called()
