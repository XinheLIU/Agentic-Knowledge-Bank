"""OpenAI-compatible LLM client used by LangGraph workflow nodes."""

from __future__ import annotations

import json
import logging
import os
import re
import time
from dataclasses import dataclass, field
from typing import Any

import httpx
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)


@dataclass
class Usage:
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
    content: str
    usage: Usage = field(default_factory=Usage)


PRICING: dict[str, dict[str, float]] = {
    "deepseek-chat": {"input": 0.0014, "output": 0.0028},
    "deepseek-reasoner": {"input": 0.004, "output": 0.016},
    "qwen-plus": {"input": 0.002, "output": 0.006},
    "qwen-turbo": {"input": 0.0005, "output": 0.001},
    "gpt-4o-mini": {"input": 0.00015, "output": 0.0006},
    "gpt-4o": {"input": 0.005, "output": 0.015},
}


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


class OpenAICompatibleProvider:
    """Minimal HTTP client for OpenAI-compatible chat completions."""

    def __init__(self, api_key: str, base_url: str, model: str):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.client = httpx.Client(timeout=60.0)

    def chat(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 2000,
    ) -> LLMResponse:
        response = self.client.post(
            f"{self.base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": self.model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
            },
        )
        response.raise_for_status()
        data = response.json()
        usage_data = data.get("usage", {})
        return LLMResponse(
            content=data["choices"][0]["message"]["content"],
            usage=Usage(
                prompt_tokens=usage_data.get("prompt_tokens", 0),
                completion_tokens=usage_data.get("completion_tokens", 0),
            ),
        )

    def close(self) -> None:
        self.client.close()

    def __enter__(self) -> "OpenAICompatibleProvider":
        return self

    def __exit__(self, *args: object) -> None:
        self.close()


def create_provider(provider_name: str | None = None) -> OpenAICompatibleProvider:
    name = (provider_name or os.getenv("LLM_PROVIDER", "qwen")).lower()
    if name not in PROVIDER_CONFIG:
        raise ValueError(f"未知的模型提供商: {name}，支持: {', '.join(PROVIDER_CONFIG)}")

    config = PROVIDER_CONFIG[name]
    api_key = os.getenv(config["api_key_env"], "")
    if not api_key:
        raise RuntimeError(f"缺少 API Key，请设置环境变量: {config['api_key_env']}")

    return OpenAICompatibleProvider(
        api_key=api_key,
        base_url=os.getenv(config["base_url_env"], config["default_base_url"]),
        model=os.getenv(config["model_env"], config["default_model"]),
    )


def estimate_cost(model: str, usage: Usage) -> float:
    prices = PRICING.get(model, {"input": 0.002, "output": 0.006})
    return (
        usage.prompt_tokens / 1000 * prices["input"]
        + usage.completion_tokens / 1000 * prices["output"]
    )


def chat_with_retry(
    provider: OpenAICompatibleProvider,
    messages: list[dict[str, str]],
    temperature: float = 0.7,
    max_tokens: int = 2000,
    max_retries: int = 3,
    backoff_base: float = 2.0,
) -> LLMResponse:
    last_error: Exception | None = None

    for attempt in range(max_retries):
        try:
            return provider.chat(messages, temperature=temperature, max_tokens=max_tokens)
        except (httpx.HTTPStatusError, httpx.ConnectError, httpx.TimeoutException) as error:
            last_error = error
            if attempt < max_retries - 1:
                time.sleep(backoff_base**attempt)

    raise last_error  # type: ignore[misc]


def parse_json_response(text: str) -> dict[str, Any] | list[Any]:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    for pattern in (r"\{[\s\S]*\}", r"\[[\s\S]*\]"):
        match = re.search(pattern, cleaned)
        if match:
            return json.loads(match.group())

    return json.loads(cleaned)


def chat_json_with_model(
    prompt: str,
    system: str = "你是一个专业的 AI 技术分析师。请只返回 JSON。",
    provider_name: str | None = None,
    temperature: float = 0.3,
    max_tokens: int = 2000,
) -> tuple[dict[str, Any] | list[Any], Usage, str]:
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": prompt},
    ]
    provider = create_provider(provider_name)
    try:
        response = chat_with_retry(
            provider,
            messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return parse_json_response(response.content), response.usage, provider.model
    finally:
        provider.close()


def chat_json(
    prompt: str,
    system: str = "你是一个专业的 AI 技术分析师。请只返回 JSON。",
    provider_name: str | None = None,
    temperature: float = 0.3,
    max_tokens: int = 2000,
) -> tuple[dict[str, Any] | list[Any], dict[str, int]]:
    result, usage, _ = chat_json_with_model(
        prompt,
        system=system,
        provider_name=provider_name,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    return result, usage.to_dict()


def chat(
    prompt: str,
    system: str = "你是一个专业的 AI 技术分析师。",
    provider_name: str | None = None,
    temperature: float = 0.3,
    max_tokens: int = 2000,
) -> tuple[str, dict[str, int]]:
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": prompt},
    ]
    provider = create_provider(provider_name)
    try:
        response = chat_with_retry(
            provider,
            messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return response.content, response.usage.to_dict()
    finally:
        provider.close()


def accumulate_usage(tracker: dict[str, Any], usage: Usage, model: str = "") -> dict[str, Any]:
    if isinstance(usage, dict):
        usage = Usage(
            prompt_tokens=int(usage.get("prompt_tokens", 0)),
            completion_tokens=int(usage.get("completion_tokens", 0)),
        )

    prompt_tokens = int(tracker.get("prompt_tokens", 0)) + usage.prompt_tokens
    completion_tokens = int(tracker.get("completion_tokens", 0)) + usage.completion_tokens
    total_cost_usd = float(tracker.get("total_cost_usd", 0.0))
    if model:
        total_cost_usd += estimate_cost(model, usage)

    return {
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_cost_usd": round(total_cost_usd, 6),
        "total_cost_yuan": round(total_cost_usd * 7.2, 6),
    }
