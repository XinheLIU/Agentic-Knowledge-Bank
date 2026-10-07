"""Prototype store seam (ticket 05).

In-memory stand-in for ticket 07's canonical SQLite asset store. The CLI
depends only on these three operations, so swapping the real store in later
does not touch the operator surface. No filesystem, no sqlite3 here.

Per the resolved asset model (ticket 02 / ADR 0001): accepted assets are
**write-once** — a re-fetched accepted asset is a ``DUPLICATE_ID`` candidate
occurrence that may no-op but must never update the stored item.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from kb.horizon.contract import map_item

__all__ = ["PrototypeStore"]

RADAR_PREFIX = "horizon"


@dataclass
class PrototypeStore:
    """In-memory asset store implementing the canonical-store seam."""

    items: dict[str, dict[str, Any]] = field(default_factory=dict)

    def upsert_items(
        self, raw_items: list[dict[str, Any]], *, languages: tuple[str, ...] | None = None
    ) -> dict[str, int]:
        """Admit items keyed by namespaced minted ID; returns decision counts.

        Write-once: an already-accepted asset makes the occurrence a
        ``DUPLICATE_ID`` no-op (no update). ``persisted`` counts occurrences
        presented; ``inserted``/``duplicates`` partition them.
        """
        inserted = 0
        duplicates = 0
        langs = list(languages) if languages is not None else None
        for raw in raw_items:
            row = map_item(raw, languages=langs)
            if row["id"] in self.items:
                duplicates += 1  # write-once: never update an accepted asset
            else:
                inserted += 1
                self.items[row["id"]] = row
        return {
            "inserted": inserted,
            "duplicates": duplicates,
            "persisted": len(raw_items),
        }

    def stats(self) -> dict[str, int]:
        return {"item_count": len(self.items)}

    def latest_published_day(self) -> str | None:
        days = [row.get("published_at", "")[:10] for row in self.items.values()]
        days = [d for d in days if d]
        return max(days) if days else None
