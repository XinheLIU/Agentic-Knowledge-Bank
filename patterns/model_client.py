"""Minimal OpenAI-compatible chat helpers for the demo patterns.

Replaces the retired ``workflows.model_client`` after the ticket-16 legacy
retirement: the demos stay importable with zero project dependencies.
"""

from __future__ import annotations

import json
import os
import urllib.request

Usage = dict


def _settings() -> tuple[str, str, str]:
    provider = os.environ.get("LLM_PROVIDER", "deepseek")
    keys = {
        "deepseek": ("DEEPSEEK_API_KEY", "https://api.deepseek.com/v1/chat/completions", "deepseek-chat"),
        "qwen": ("DASHSCOPE_API_KEY", "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions", "qwen-plus"),
        "openai": ("OPENAI_API_KEY", "https://api.openai.com/v1/chat/completions", "gpt-4o-mini"),
    }
    env_key, url, model = keys[provider]
    api_key = os.environ.get(env_key, "")
    return api_key, url, model


def chat(prompt: str, system: str = "") -> tuple[str, Usage]:
    """Send a chat completion; return (text, usage). Raises on missing config."""
    api_key, url, model = _settings()
    if not api_key:
        raise RuntimeError("LLM API key not configured (set LLM_PROVIDER + provider key)")
    messages = ([{"role": "system", "content": system}] if system else []) + [
        {"role": "user", "content": prompt}
    ]
    req = urllib.request.Request(
        url,
        data=json.dumps({"model": model, "messages": messages}).encode(),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        payload = json.loads(resp.read())
    return payload["choices"][0]["message"]["content"], payload.get("usage", {})


def chat_json(prompt: str, system: str = "") -> tuple[dict, Usage]:
    """chat() + JSON parse of the response text."""
    text, usage = chat(prompt, system=system)
    return json.loads(text), usage


def accumulate_usage(total: dict | None, add: dict) -> dict:
    """Accumulate token usage dicts."""
    total = dict(total or {})
    for key, value in add.items():
        if isinstance(value, (int, float)):
            total[key] = total.get(key, 0) + value
    return total
