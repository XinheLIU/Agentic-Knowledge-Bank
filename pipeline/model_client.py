"""
Unified LLM client for OpenAI-compatible chat completion providers.

DeepSeek, Qwen, and OpenAI are selected through environment variables.
Responses are normalized to {"content": str, "usage": {...}}.
"""

from __future__ import annotations

import os
import time
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

import httpx
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

@dataclass
class Usage:
    """Token usage statistics."""
    prompt_tokens: int = 0
    completion_tokens: int = 0

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens

    def to_dict(self) -> dict[str, int]:
        return {
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
        }


@dataclass
class LLMResponse:
    """Normalized LLM response."""
    content: str
    usage: Usage = field(default_factory=Usage)

    def to_dict(self) -> dict[str, Any]:
        return {
            "content": self.content,
            "usage": self.usage.to_dict(),
        }


PRICING: dict[str, dict[str, float]] = {
    "deepseek-chat": {"input": 0.0014, "output": 0.0028},
    "deepseek-reasoner": {"input": 0.004, "output": 0.016},
    "qwen-plus": {"input": 0.002, "output": 0.006},
    "qwen-turbo": {"input": 0.0005, "output": 0.001},
    "gpt-4o-mini": {"input": 0.00015, "output": 0.0006},
    "gpt-4o": {"input": 0.005, "output": 0.015},
}


def estimate_cost(model: str, usage: Usage) -> float:
    """Estimate the cost for one call in USD."""
    prices = PRICING.get(model, {"input": 0.002, "output": 0.006})
    return (
        usage.prompt_tokens / 1000 * prices["input"]
        + usage.completion_tokens / 1000 * prices["output"]
    )


class LLMProvider(ABC):
    """Base class for LLM providers."""

    def __init__(self, api_key: str, base_url: str, model: str):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.client = httpx.Client(timeout=60.0)

    @abstractmethod
    def chat(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 2000,
    ) -> LLMResponse:
        """Send a chat request and return a normalized response."""
        ...

    def close(self) -> None:
        self.client.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


class OpenAICompatibleProvider(LLMProvider):
    """
    Provider for APIs compatible with OpenAI Chat Completions.

    DeepSeek, Qwen, and OpenAI use the same request and response shape here.
    """

    def chat(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 2000,
    ) -> LLMResponse:
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        resp = self.client.post(url, json=payload, headers=headers)
        resp.raise_for_status()
        data = resp.json()

        content = data["choices"][0]["message"]["content"]
        usage_data = data.get("usage", {})
        usage = Usage(
            prompt_tokens=usage_data.get("prompt_tokens", 0),
            completion_tokens=usage_data.get("completion_tokens", 0),
        )

        return LLMResponse(content=content, usage=usage)


PROVIDER_CONFIG: dict[str, dict[str, str]] = {
    "deepseek": {
        "api_key_env": "DEEPSEEK_API_KEY",
        "base_url_env": "DEEPSEEK_BASE_URL",
        "model_env": "DEEPSEEK_MODEL",
        "default_base_url": "https://api.deepseek.com",
        "default_model": "deepseek-chat",
    },
    "qwen": {
        "api_key_env": "DASHSCOPE_API_KEY",
        "base_url_env": "QWEN_BASE_URL",
        "model_env": "QWEN_MODEL",
        "default_base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "default_model": "qwen-plus",
    },
    "openai": {
        "api_key_env": "OPENAI_API_KEY",
        "base_url_env": "OPENAI_BASE_URL",
        "model_env": "OPENAI_MODEL",
        "default_base_url": "https://api.openai.com/v1",
        "default_model": "gpt-4o-mini",
    },
}


def create_provider(provider_name: str | None = None) -> LLMProvider:
    """
    Create an LLM client for the requested provider.

    Args:
        provider_name: Provider name (deepseek/qwen/openai). Defaults to LLM_PROVIDER.

    Returns:
        LLM provider instance.

    Raises:
        ValueError: The provider name is unknown.
        RuntimeError: The required API key is missing.
    """
    name = (provider_name or os.getenv("LLM_PROVIDER", "qwen")).lower()

    if name not in PROVIDER_CONFIG:
        raise ValueError(
            f"未知的模型提供商: {name}，支持: {', '.join(PROVIDER_CONFIG.keys())}"
        )

    config = PROVIDER_CONFIG[name]
    api_key = os.getenv(config["api_key_env"], "")
    if not api_key:
        raise RuntimeError(
            f"缺少 API Key，请设置环境变量: {config['api_key_env']}"
        )

    base_url = os.getenv(config["base_url_env"], config["default_base_url"])
    model = os.getenv(config["model_env"], config["default_model"])

    logger.info("创建 LLM 客户端: provider=%s, model=%s", name, model)
    return OpenAICompatibleProvider(api_key=api_key, base_url=base_url, model=model)


def chat_with_retry(
    provider: LLMProvider,
    messages: list[dict[str, str]],
    temperature: float = 0.7,
    max_tokens: int = 2000,
    max_retries: int = 3,
    backoff_base: float = 2.0,
) -> LLMResponse:
    """
    Call chat with exponential backoff retries.

    Args:
        provider: LLM provider instance.
        messages: Chat messages.
        temperature: Sampling temperature.
        max_tokens: Maximum generated tokens.
        max_retries: Maximum number of attempts.
        backoff_base: Backoff base in seconds.

    Returns:
        Normalized LLM response.

    Raises:
        The final retry exception.
    """
    last_error: Exception | None = None

    for attempt in range(max_retries):
        try:
            response = provider.chat(
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            if attempt > 0:
                logger.info("第 %d 次重试成功", attempt)
            return response

        except (httpx.HTTPStatusError, httpx.ConnectError, httpx.TimeoutException) as e:
            last_error = e
            if attempt < max_retries - 1:
                wait_time = backoff_base ** attempt
                logger.warning(
                    "LLM 调用失败（第 %d/%d 次），%0.1f 秒后重试: %s",
                    attempt + 1, max_retries, wait_time, str(e),
                )
                time.sleep(wait_time)
            else:
                logger.error("LLM 调用失败，已达最大重试次数: %s", str(e))

    raise last_error  # type: ignore[misc]


def quick_chat(
    prompt: str,
    system: str = "你是一个 AI 技术分析助手。",
    provider_name: str | None = None,
) -> str:
    """
    Send one prompt and return the response text.

    Args:
        prompt: User prompt.
        system: System prompt.
        provider_name: Provider name. Defaults to environment configuration.

    Returns:
        LLM response text.
    """
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": prompt},
    ]

    provider = create_provider(provider_name)
    try:
        response = chat_with_retry(provider, messages)
        cost = estimate_cost(provider.model, response.usage)
        logger.info(
            "Token 用量: %d (prompt) + %d (completion) = %d, 估算成本: $%.6f",
            response.usage.prompt_tokens,
            response.usage.completion_tokens,
            response.usage.total_tokens,
            cost,
        )
        return response.content
    finally:
        provider.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    print("=== LLM 客户端测试 ===")
    print(f"提供商: {os.getenv('LLM_PROVIDER', 'qwen')}")

    try:
        result = quick_chat("用一句话介绍什么是 AI Agent。")
        print(f"\n回复: {result}")
    except Exception as e:
        print(f"\n错误: {e}")
        print("请检查 .env 文件中的 API Key 配置。")
