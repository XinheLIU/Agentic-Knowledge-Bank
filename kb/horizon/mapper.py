"""Pure ``ContentItem`` mapper (ticket 08): Horizon item -> typed store input.

Ticket 08's acceptance criteria add to the ticket-05 vocabulary in
:func:`kb.horizon.contract.map_item`:

- Unknown upstream fields are preserved only in *bounded* metadata: a size-
  and depth-capped projection of everything not explicitly mapped, so new
  upstream fields survive auditable but cannot blow up a row.
- Missing required fields (``id``, ``title``, ``url``, ``published_at`` —
  non-null upstream at the pinned commit) fail with an auditable reason:
  a :class:`MappingFailure` carrying a registered ``MAP_FAILED``-family
  reason code, never a silent default.

Pure functions only: no I/O, no store, no transport, no Horizon imports.
"""

from __future__ import annotations

import json
from typing import Any

from kb.horizon.contract import mint_asset_id
from kb.model import ReasonCode

__all__ = [
    "MAP_FAILED_CODE",
    "METADATA_MAX_BYTES",
    "MappingFailure",
    "map_content_item",
    "required_field_failure",
]

#: Registry code (kb/model.py, TRANSPORT_MAPPING namespace) attached to every
#: mapping failure — one vocabulary, no second declaration (O2).
MAP_FAILED_CODE = "MAP_FAILED"

#: Bound for the preserved unknown-fields metadata blob, in bytes of compact
#: JSON. Anything larger is dropped (recorded, not silently truncated
#: mid-string).
METADATA_MAX_BYTES = 8 * 1024

#: Depth bound for the unknown-fields projection (bounded metadata guarantee).
_METADATA_MAX_DEPTH = 6

_REQUIRED_FIELDS = ("id", "title", "url", "published_at")


class MappingFailure(Exception):
    """A Horizon item could not be mapped; auditable, non-terminal.

    The admission ledger records outcome ``failed`` with this item's
    ``reason_code`` (ticket 03: mapper failure => ledger ``failed`` with
    ``["MAP_FAILED"]``; the next run re-decides without a refetch).
    """

    def __init__(self, item_id: str | None, reason: str,
                 reason_code: str = MAP_FAILED_CODE) -> None:
        super().__init__(f"item {item_id!r}: {reason}")
        self.item_id = item_id
        self.reason = reason
        self.reason_code = reason_code
        if not ReasonCode.is_registered(reason_code):
            raise ValueError(f"reason code {reason_code!r} is not in the kb/model.py registry")


def required_field_failure(item_id: str | None, field: str) -> MappingFailure:
    """Auditable failure for a missing/empty required ``ContentItem`` field.

    ``published_at`` is non-null upstream at the pin; a fixture without it is
    a broken capture, so it fails auditably rather than mapping to ``NULL``.
    """
    return MappingFailure(item_id, f"missing required field {field!r}")


def _bounded(value: Any, *, depth: int = 0) -> Any:
    """Project a JSON value with size/depth bounds (returns ``None`` if over).

    Whole-value bound: a projected subtree is kept only if its compact JSON
    encoding fits in :data:`METADATA_MAX_BYTES` — a scalar or structure that
    is too large is dropped entirely (auditable absence, never a mid-string
    truncation that would corrupt evidence).
    """
    if depth > _METADATA_MAX_DEPTH:
        return None
    if isinstance(value, (str, int, float, bool)) or value is None:
        if value is not None and len(
            json.dumps(value, ensure_ascii=False).encode("utf-8")
        ) > METADATA_MAX_BYTES:
            return None
        return value
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for key in sorted(value, key=str)[:64]:
            child = _bounded(value[key], depth=depth + 1)
            if child is not None:
                out[str(key)] = child
        return out or None
    if isinstance(value, list):
        items = [
            child
            for child in (_bounded(v, depth=depth + 1) for v in value[:64])
            if child is not None
        ]
        return items or None
    return None


def _unknown_fields(raw: dict[str, Any], mapped_keys: set[str]) -> dict[str, Any] | None:
    extras = {k: v for k, v in raw.items() if k not in mapped_keys}
    if not extras:
        return None
    return _bounded(extras)  # type: ignore[return-value]


def map_content_item(
    raw: dict[str, Any], *, languages: list[str] | None = None
) -> dict[str, Any]:
    """Map one Horizon ``ContentItem`` dict to typed store-input fields.

    Same row vocabulary as :func:`kb.horizon.contract.map_item` (ticket 05),
    extended with ticket 08 guarantees:

    - ``id`` minted once as ``horizon:<opaque Horizon id>`` (ADR 0001).
    - required fields (``id``/``title``/``url``/``published_at``) must be
      present and non-empty; absence raises :class:`MappingFailure`.
    - unknown upstream fields are preserved only inside ``metadata_json`` as
      a bounded ``horizon_extra`` projection (size- and depth-capped).
    - artifact languages pass through open-ended; ``languages`` filters which
      artifacts are kept (all when ``None``).
    - block ``position`` is derived from list order (no upstream field).
    """
    if not isinstance(raw, dict):
        raise MappingFailure(None, "ContentItem capture is not a JSON object")
    if "id" not in raw or not str(raw.get("id") or "").strip():
        raise required_field_failure(None, "id")
    horizon_id = str(raw["id"])
    for field in ("title", "url", "published_at"):
        value = raw.get(field)
        if not isinstance(value, str) or not value.strip():
            raise required_field_failure(horizon_id, field)

    mapped_keys = {
        "id", "source_type", "title", "url", "author", "published_at",
        "fetched_at", "profile", "processing", "metadata",
    }
    processing = raw.get("processing") or {}
    classification = processing.get("classification") or {}
    analysis = processing.get("analysis") or {}
    metadata = raw.get("metadata")
    extras = _unknown_fields(raw, mapped_keys)

    mapped: dict[str, Any] = {
        "id": mint_asset_id(horizon_id),
        "source_type": raw.get("source_type"),
        "title": raw["title"],
        "url": raw["url"],
        "author": raw.get("author"),
        "published_at": raw["published_at"],
        "fetched_at": raw.get("fetched_at"),
        "profile": classification.get("profile"),
        "profile_method": classification.get("method"),
        "profile_confidence": classification.get("confidence"),
        "profile_reason": classification.get("reason"),
        "score": analysis.get("score"),
        "score_reason": analysis.get("reason"),
        "summary": analysis.get("summary"),
        "tags": sorted({str(tag) for tag in (analysis.get("tags") or []) if str(tag).strip()}),
        "content_main": raw.get("content"),
        "content_comments": raw.get("comments"),
        "metadata_json": metadata if isinstance(metadata, (dict, list)) else (
            {"value": metadata} if metadata is not None else None
        ),
        "horizon_extra": extras,
        "artifacts": [],
    }

    artifact_map = processing.get("artifacts") or {}
    if languages is not None:
        wanted = set(languages)
        artifact_map = {k: v for k, v in artifact_map.items() if k in wanted}
    for language, artifact in artifact_map.items():
        blocks: list[dict[str, Any]] = []
        for position, block in enumerate(artifact.get("blocks") or []):
            blocks.append({
                "block_id": block.get("id"),
                "title": block.get("title"),
                "content": block.get("content"),
                "is_primary": bool(block.get("primary")),
                "position": position,
                "source_ids": list(block.get("source_refs") or []),
            })
        mapped["artifacts"].append({
            "language": language,
            "title": artifact.get("title"),
            "blocks": blocks,
        })
    return mapped
