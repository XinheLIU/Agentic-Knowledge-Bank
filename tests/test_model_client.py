"""Tests for workflows/model_client.py"""

import os
from unittest.mock import MagicMock, patch

import httpx
import pytest

from workflows.model_client import (
    LLMResponse,
    OpenAICompatibleProvider,
    Usage,
    parse_json_response,
    chat_with_retry,
    create_provider,
    estimate_cost,
)

pytestmark = pytest.mark.non_llm


class TestCreateProvider:
    def test_missing_api_key_raises_runtime_error(self):
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(RuntimeError, match="DEEPSEEK_API_KEY"):
                create_provider("deepseek")

    def test_unknown_provider_raises_value_error(self):
        with pytest.raises(ValueError, match="未知的模型提供商"):
            create_provider("nonexistent")

    def test_creates_deepseek_provider(self):
        with patch.dict(
            os.environ,
            {"DEEPSEEK_API_KEY": "sk-test", "LLM_PROVIDER": ""},
            clear=False,
        ):
            provider = create_provider("deepseek")
            assert isinstance(provider, OpenAICompatibleProvider)
            assert provider.model == "deepseek-chat"
            provider.close()

    def test_reads_from_llm_provider_env(self):
        with patch.dict(
            os.environ,
            {"LLM_PROVIDER": "openai", "OPENAI_API_KEY": "sk-test"},
            clear=False,
        ):
            provider = create_provider()
            assert isinstance(provider, OpenAICompatibleProvider)
            assert provider.model == "gpt-4o-mini"
            provider.close()

    def test_defaults_to_qwen_when_no_env_set(self):
        with patch.dict(
            os.environ,
            {"DASHSCOPE_API_KEY": "sk-test"},
            clear=True,
        ):
            provider = create_provider()
            assert isinstance(provider, OpenAICompatibleProvider)
            assert provider.model == "qwen-plus"
            provider.close()


class TestEstimateCost:
    def test_deepseek_chat(self):
        usage = Usage(prompt_tokens=1000, completion_tokens=500)
        cost = estimate_cost("deepseek-chat", usage)
        expected = (1000 / 1000 * 0.0014) + (500 / 1000 * 0.0028)
        assert cost == pytest.approx(expected, rel=1e-6)

    def test_unknown_model_uses_default_pricing(self):
        usage = Usage(prompt_tokens=1000, completion_tokens=500)
        cost = estimate_cost("unknown-model", usage)
        expected = (1000 / 1000 * 0.002) + (500 / 1000 * 0.006)
        assert cost == pytest.approx(expected, rel=1e-6)


class TestChatWithRetry:
    def test_success_on_first_attempt(self, mocker):
        provider = MagicMock(spec=OpenAICompatibleProvider)
        provider.chat.return_value = LLMResponse(
            content="hello", usage=Usage(prompt_tokens=10, completion_tokens=5)
        )

        response = chat_with_retry(provider, messages=[{"role": "user", "content": "hi"}])
        assert response.content == "hello"
        assert provider.chat.call_count == 1

    def test_retry_on_http_error_then_success(self, mocker):
        provider = MagicMock(spec=OpenAICompatibleProvider)
        provider.chat.side_effect = [
            httpx.HTTPStatusError(
                "Rate limited",
                request=MagicMock(),
                response=MagicMock(status_code=429),
            ),
            LLMResponse(content="hello", usage=Usage()),
        ]

        with patch("workflows.model_client.time.sleep", return_value=None):
            response = chat_with_retry(provider, messages=[{"role": "user", "content": "hi"}])

        assert response.content == "hello"
        assert provider.chat.call_count == 2

    def test_raises_after_max_retries(self, mocker):
        provider = MagicMock(spec=OpenAICompatibleProvider)
        provider.chat.side_effect = httpx.ConnectError("Connection refused")

        with patch("workflows.model_client.time.sleep", return_value=None):
            with pytest.raises(httpx.ConnectError):
                chat_with_retry(
                    provider,
                    messages=[{"role": "user", "content": "hi"}],
                    max_retries=2,
                )

        assert provider.chat.call_count == 2


class TestUsage:
    def test_total_tokens(self):
        u = Usage(prompt_tokens=10, completion_tokens=5)
        assert u.total_tokens == 15

    def test_to_dict(self):
        u = Usage(prompt_tokens=10, completion_tokens=5)
        assert u.to_dict() == {
            "prompt_tokens": 10,
            "completion_tokens": 5,
            "total_tokens": 15,
        }


class TestParseJsonResponse:
    def test_parses_markdown_wrapped_json(self):
        result = parse_json_response("```json\n{\"ok\": true}\n```")
        assert result == {"ok": True}

    def test_parses_json_with_surrounding_text(self):
        result = parse_json_response("answer:\n{\"score\": 7}\nthanks")
        assert result == {"score": 7}
