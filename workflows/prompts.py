"""Prompt template loader.

Prompts live as plain-text files under ``prompts/`` instead of inline in the
nodes. A provider-specific file (``prompts/<provider>/<name>.txt``) overrides
the generic one (``prompts/<name>.txt``) when present, so a future cheaper or
terser model can ship its own variant without touching node code.

Substitution uses ``string.Template`` (``$placeholder``) rather than
``str.format`` because the prompts are full of literal JSON ``{}`` braces.
"""

from __future__ import annotations

import os
from pathlib import Path
from string import Template

PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"

_cache: dict[tuple[str, str], str] = {}


def load_prompt(name: str, provider: str | None = None) -> str:
    """Return raw template text for ``name``.

    Resolves ``prompts/<provider>/<name>.txt`` first, then falls back to the
    generic ``prompts/<name>.txt``. Results are cached per (name, provider).
    Raises ``FileNotFoundError`` if neither file exists.
    """
    prov = (provider or os.getenv("LLM_PROVIDER", "qwen")).lower()
    cache_key = (name, prov)
    if cache_key in _cache:
        return _cache[cache_key]

    candidates = [PROMPTS_DIR / prov / f"{name}.txt", PROMPTS_DIR / f"{name}.txt"]
    for path in candidates:
        if path.exists():
            text = path.read_text(encoding="utf-8")
            _cache[cache_key] = text
            return text

    raise FileNotFoundError(
        f"Prompt template '{name}' not found (looked in {[str(p) for p in candidates]})"
    )


def render(name: str, mapping: dict[str, str], provider: str | None = None) -> str:
    """Load template ``name`` and substitute ``$placeholders`` from ``mapping``.

    Uses ``Template.substitute`` so a missing placeholder raises ``KeyError``
    rather than silently leaving ``$var`` in the prompt.
    """
    return Template(load_prompt(name, provider)).substitute(mapping)
