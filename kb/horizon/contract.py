"""KB-owned asset mapping contract and storage-operator summaries.

Owns the part of the old operator surface that belongs to the knowledge base
itself rather than to collection:

- :func:`mint_asset_id` — the canonical ``horizon:<opaque id>`` asset ID
  (ADR 0001): minted once, verbatim, never re-derived.
- :func:`map_item` — the prototype pure mapper from a Horizon ``ContentItem``
  dict to canonical asset-row fields; it fixes the row vocabulary shared with
  the production mapper :mod:`kb.horizon.mapper`.
- the storage-command summaries (``serve`` / ``export`` / ``backup`` /
  ``restore``) printed as machine-readable one-liners by :mod:`kb.cli`.

Run-lifecycle vocabulary (stages, deadlines, run status) and the run/digest
summaries belong to the collection owner and are supplied by ``agent-tools``
and Information Assistant; KB consumes a completed payload through
:func:`kb.ingest.ingest_horizon_payload`.

This module is dataclasses + pure functions only: no I/O, no MCP, no store.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from agent_tools.horizon.contract import ExitCode, selected_profile, summary

__all__ = [
    "HORIZON_ID_PREFIX",
    "ExitCode",
    "BackupSummary",
    "RestoreSummary",
    "ServeSummary",
    "ExportSummary",
    "summary",
    "selected_profile",
    "map_item",
]

#: Radar namespace minted onto every accepted asset ID per ADR 0001
#: (ticket 02): ``horizon:<opaque Horizon id>``. Horizon IDs are opaque and may
#: themselves contain colons, so the namespace is the FIRST colon-separated
#: component — never re-derived from a format assumption.
HORIZON_ID_PREFIX = "horizon"


def mint_asset_id(horizon_id: str) -> str:
    """Mint the canonical asset ID: ``horizon:<opaque Horizon id>``.

    Pure and total: the Horizon ID is stored verbatim (colons legal); the
    prefix is prepended unconditionally — an input that already contains
    colons is NOT treated as pre-namespaced.
    """
    return f"{HORIZON_ID_PREFIX}:{horizon_id}"










# ---------------------------------------------------------------------------
# Structured summaries (machine-readable payload printed by every command)
# ---------------------------------------------------------------------------




@dataclass
class BackupSummary:
    """Result of SQLite asset-store backup (consistent snapshot)."""

    path: str
    size_bytes: int
    item_count: int
    consistent: bool = True

    def to_payload(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "size_bytes": self.size_bytes,
            "item_count": self.item_count,
            "consistent": self.consistent,
        }


@dataclass
class RestoreSummary:
    """Result of restore; ``dry_run`` validates without writing."""

    path: str
    restored: bool
    dry_run: bool
    item_count: int

    def to_payload(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "restored": self.restored,
            "dry_run": self.dry_run,
            "item_count": self.item_count,
        }


@dataclass
class ServeSummary:
    """Result of serve launch; ``mode`` records the declared transport."""

    mode: str
    host: str
    port: int

    def to_payload(self) -> dict[str, Any]:
        return {"mode": self.mode, "host": self.host, "port": self.port}


@dataclass
class ExportSummary:
    """Result of JSONL snapshot export."""

    path: str
    item_count: int
    format: str = "jsonl"

    def to_payload(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "item_count": self.item_count,
            "format": self.format,
        }




# ---------------------------------------------------------------------------
# Pure policies — the corrected design's decision points
# ---------------------------------------------------------------------------








def map_item(raw: dict[str, Any], *, languages: list[str] | None = None) -> dict[str, Any]:
    """Map one Horizon ``ContentItem`` dict to canonical asset-row fields.

    Pure (no I/O) so ticket 08's real mapper can be verified against this
    vocabulary. Corrections applied:

    - ``id`` is minted as ``horizon:<opaque Horizon id>`` (ADR 0001); the
      Horizon ID is verbatim — already-colon-containing IDs are not treated
      as pre-namespaced.
    - ``profile`` stored from ``processing.classification.profile``.
    - artifact language keys passed through as-is (not limited to en/zh);
      ``languages`` restricts which artifacts are kept when given (e.g. the
      CLI's ``--language`` digest target), defaulting to all.
    - ``position`` derived from list order; upstream has no such field.
    """
    processing = raw.get("processing") or {}
    classification = processing.get("classification") or {}
    analysis = processing.get("analysis") or {}

    mapped: dict[str, Any] = {
        "id": mint_asset_id(raw["id"]),
        "source_type": raw["source_type"],
        "title": raw["title"],
        "url": raw["url"],
        "author": raw.get("author"),
        "published_at": raw.get("published_at"),
        "fetched_at": raw.get("fetched_at"),
        "profile": selected_profile(raw),
        "profile_method": classification.get("method"),
        "profile_confidence": classification.get("confidence"),
        "profile_reason": classification.get("reason"),
        "score": analysis.get("score"),
        "score_reason": analysis.get("reason"),
        "summary": analysis.get("summary"),
        "tags": sorted(set(analysis.get("tags") or [])),
        "metadata_json": raw.get("metadata"),
        "artifacts": [],
    }

    artifact_map = processing.get("artifacts") or {}
    if languages is not None:
        wanted = set(languages)
        artifact_map = {k: v for k, v in artifact_map.items() if k in wanted}
    for language, artifact in artifact_map.items():
        artifacts = mapped["artifacts"]
        entry: dict[str, Any] = {"language": language, "title": artifact.get("title"), "blocks": []}
        for position, block in enumerate(artifact.get("blocks") or []):
            entry["blocks"].append(
                {
                    "block_id": block.get("id"),
                    "title": block.get("title"),
                    "content": block.get("content"),
                    "is_primary": bool(block.get("primary")),
                    "position": position,
                    "source_ids": list(block.get("source_refs") or []),
                }
            )
        artifacts.append(entry)
    return mapped
