"""Auditable admission of a provider payload (ticket 10).

KB consumes an already-completed collection outcome: it never runs the
provider, spawns a transport, or schedules collection. Run orchestration lives
with the collection owner (Information Assistant); this module owns the KB
half — map, admit, account, persist:

- :func:`kb.horizon.mapper.map_content_item` — typed mapping; every mapping
  failure becomes an explicit ``failed`` ledger outcome (never silent).
- :func:`kb.admission.policy.admit` — pure per-item admission with dedup state
  built from the store.
- :meth:`kb.store.model.AssetStore.ingest_run` — atomic persistence with
  I2/I3 invariant checks and idempotent replay (precedence 0).

The accepted payload is the named artifact between the two products. It is
the collection owner's job to resolve it; KB only reads it:

- ``run_id`` — the provider's run identity.
- ``radar_ref`` — the pinned provider revision the run was produced against.
  **Required.** Only the producer knows which checkout produced the run, so a
  payload without it is refused rather than recorded against a guessed pin.
- ``stages_present`` / ``stage_payloads`` — the collected items; KB reads them
  at the highest persisted stage.
- optional ``fetch_status`` / ``enrich_result`` — run-status signals.

Every input item ends in exactly one terminal ledger outcome: accepted,
rejected, or failed. Re-running the same run (or the same stories) mutates
nothing: replayed assets are ``DUPLICATE_ID`` no-ops against the append-only
ledger, and a finished run replays as a pure no-op inside ``ingest_run``.
"""

from __future__ import annotations

from typing import Any

from agent_tools.horizon.contract import highest_stage
from kb.admission.policy import AdmissionDecision, AdmissionPolicy, DedupState, admit
from kb.horizon.mapper import MappingFailure, map_content_item
from kb.model import story_fingerprint
from kb.store.model import AssetStore

__all__ = ["ingest_horizon_payload"]


def _payload_radar_ref(outcome: dict[str, Any]) -> str:
    """Read the provider revision recorded for the run; never guess one.

    ``radar_ref`` belongs to the payload because only the producer knows which
    pinned provider checkout the run came from. Substituting a local constant
    would silently attribute the run to the wrong revision, so a missing or
    blank reference is refused instead.
    """
    ref = outcome.get("radar_ref")
    if not isinstance(ref, str) or not ref.strip():
        raise ValueError(
            "provider payload must carry a non-empty string 'radar_ref' (the "
            "pinned provider revision the run was produced against); refusing "
            "to record an unverified reference"
        )
    return ref


def _dedup_state(store: AssetStore, decided: list[AdmissionDecision]) -> DedupState:
    """Store knowledge + decisions made earlier in this run (policy §2.4)."""
    item_ids = [d.item_id for d in decided]
    urls = [str(d.evidence.get("url") or "") for d in decided if d.evidence.get("url")]
    for item in store.list_items(limit=None):
        item_ids.append(item.id)
        if item.url:
            urls.append(item.url)
    return DedupState(decided_item_ids=tuple(item_ids), decided_urls=tuple(urls))


def ingest_horizon_payload(
    outcome: dict[str, Any],
    store: AssetStore,
    *,
    languages: list[str] | None = None,
    policy: AdmissionPolicy | None = None,
) -> dict[str, Any]:
    """Admit a completed provider payload; no collection or transport calls.

    Raises :class:`ValueError` when the payload carries no ``radar_ref``: run
    identity must be delivered by the producer, never inferred here.
    """
    resolved_id = str(outcome["run_id"])
    radar_ref = _payload_radar_ref(outcome)
    present: list[str] = outcome["stages_present"]
    stage_payloads: dict[str, dict[str, Any]] = outcome["stage_payloads"]
    raw_items: list[dict[str, Any]] = (
        stage_payloads.get(highest_stage(present), {}).get("items", [])
        if present
        else []
    )

    # Map: every raw item either maps or yields an explicit failed outcome.
    mapped: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    for position, raw in enumerate(raw_items):
        try:
            mapped.append(map_content_item(raw, languages=languages))
        except MappingFailure as exc:
            item_id = str(getattr(exc, "item_id", None) or f"unmapped#{position}")
            failures.append({
                "item_id": item_id,
                "outcome": "failed",
                "reason_codes": [exc.reason_code],
            })

    # Admit: pure per-item decisions; dedup includes store state and the
    # decisions already made in this run.
    active_policy = policy or AdmissionPolicy()
    decided: list[AdmissionDecision] = []
    for item in mapped:
        decision = admit(item, active_policy, dedup=_dedup_state(store, decided))
        decision.evidence.setdefault("url", item.get("url"))
        decision.evidence.setdefault("story_fp", story_fingerprint(
            str(item.get("title") or ""), str(item.get("url") or "")))
        decided.append(decision)

    accepted = [item for item, d in zip(mapped, decided) if d.accepted]
    rejections = [d.to_row() for d in decided if not d.accepted] + failures

    ledger_counts = {
        "fetched": len(raw_items),
        "mapped": len(mapped),
        "accepted": sum(1 for d in decided if d.accepted),
        "rejected": sum(1 for d in decided if d.outcome == "rejected"),
        "failed": len(failures),
    }

    run_status = (
        "empty" if not raw_items
        else "partial_failure" if (
            (outcome.get("enrich_result") or {}).get("status") == "partial"
            or outcome.get("fetch_status") == "partial_failure"
        )
        else "success"
    )

    # Precedence 0 (asset model §1.2): a run_id that already finished replays
    # as a pure no-op — return the stored accounting without re-appending any
    # ledger rows (the admissions ledger is append-only).
    existing = store.get_run(resolved_id)
    if existing is not None and existing.finished_at is not None:
        return {
            "run_id": resolved_id,
            "stages_present": present,
            "counts": {
                "fetched": existing.fetched,
                "mapped": existing.mapped,
                "accepted": existing.accepted,
                "rejected": existing.rejected,
                "failed": existing.failed,
                "persisted": existing.persisted,
            },
            "ledger": {
                "accepted": existing.accepted,
                "rejected": existing.rejected,
                "failed": existing.failed,
            },
            "duplicates": 0,
            "invariant_ok": existing.invariant_ok,
            "empty": existing.fetched == 0,
            "status": run_status,
            "radar_ref": existing.radar_ref,
            "failed_ids": [],
            "replayed": True,
        }

    run_payload = {
        "run_id": resolved_id,
        "radar": "horizon",
        "radar_ref": radar_ref,
        "status": "success" if run_status == "empty" else run_status,
        "fetched": 0 if not raw_items else ledger_counts["fetched"],
        "mapped": 0 if not raw_items else ledger_counts["mapped"],
    }
    result = store.ingest_run(run_payload, accepted, rejections)
    result["empty"] = not raw_items

    summary: dict[str, Any] = {
        "run_id": resolved_id,
        "stages_present": present,
        "counts": {
            **ledger_counts,
            "persisted": result.get("inserted", 0),
        },
        "ledger": result.get("ledger", {}),
        "duplicates": result.get("duplicates", 0),
        "invariant_ok": result.get("invariant_ok", True),
        "empty": not raw_items,
        "status": run_status,
        "radar_ref": radar_ref,
        "failed_ids": [row["item_id"] for row in failures],
    }
    return summary
