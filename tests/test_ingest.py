"""Ticket 10 tests — auditable admission of a completed provider payload.

KB no longer runs the provider: these tests drive
:func:`kb.ingest.ingest_horizon_payload` with synthetic provider payloads, so
no transport, subprocess or network is involved. Run-level concerns (stage
deadlines, resume-without-refetch) are owned and tested by the collection
side; this file covers the KB half: invariant-checked accounting,
exactly-one-terminal-outcome per item, mapping failures as ``failed`` ledger
rows, idempotent replay (same run / same stories), payload-carried run
identity, and one minted ID traced through accepted, rejected and retrieved
paths (G1/G2).
"""

from __future__ import annotations

import pytest

from kb.ingest import ingest_horizon_payload
from kb.store.model import AssetStore

pytestmark = pytest.mark.non_llm

RUN_ID = "run-abc123"

#: Pin the fake provider revision this suite claims to have produced runs with.
PIN = "596e2b1"

#: Stage lifecycle order; the payload places items at its highest stage.
_STAGES = ("raw", "scored", "filtered", "enriched")


def _raw_item(n: int = 1, **extra) -> dict:
    item = {
        "id": f"github:acme:repo-{n}",
        "source_type": "github",
        "title": f"Agent engineering repo {n}",
        "url": f"https://example.com/repo-{n}",
        "author": None,
        "published_at": "2026-09-11T08:00:00+00:00",
        "fetched_at": "2026-09-11T09:00:00+00:00",
        "content": "body",
        "processing": {
            "classification": {
                "profile": "tech-news", "method": "ai_match",
                "confidence": 0.9, "reason": "matches P0",
            },
            "analysis": {"score": 8, "reason": "relevant",
                         "summary": "mcp tooling with real mechanism"},
            "artifacts": {},
        },
        "metadata": {"stars": 42},
    }
    item.update(extra)
    return item


def _payload(
    items: list[dict], *, run_id: str = RUN_ID, stage: str = "filtered",
    radar_ref: str = PIN, **extra
) -> dict:
    """Build a provider payload with ``items`` at its highest stage."""
    present = list(_STAGES[: _STAGES.index(stage) + 1])
    payload = {
        "run_id": run_id,
        "radar_ref": radar_ref,
        "stages_present": present,
        "stage_payloads": {s: {"items": items} for s in present},
        "fetch_status": "success",
        "enrich_result": None,
    }
    payload.update(extra)
    return payload


@pytest.fixture()
def store() -> AssetStore:
    return AssetStore.open(":memory:")


def _ingest(payload: dict, store: AssetStore, **kw):
    return ingest_horizon_payload(payload, store, **kw)


class TestAccountingAndInvariants:
    def test_counts_close_and_items_persisted(self, store):
        summary = _ingest(_payload([_raw_item(1), _raw_item(2)]), store)
        assert summary["run_id"] == RUN_ID
        assert summary["status"] == "success"
        assert summary["counts"]["fetched"] == 2
        assert summary["counts"]["mapped"] == 2
        assert summary["ledger"] == {"accepted": 2, "rejected": 0, "failed": 0}
        assert summary["counts"]["persisted"] == 2
        assert summary["invariant_ok"] is True
        run = store.get_run(RUN_ID)
        assert run is not None
        assert run.fetched == run.mapped == run.persisted == 2
        assert run.accepted == 2
        assert store.stats().item_count == 2

    def test_every_item_exactly_one_terminal_outcome(self, store):
        raw = [
            _raw_item(1),
            # Guaranteed policy rejection: analysis.score missing → MISSING_SCORE
            _raw_item(2, processing={"classification": {
                "profile": "tech-news", "method": "ai_match",
                "confidence": 0.9, "reason": "matches P0",
            }}),
            _raw_item(3),
        ]
        raw[2] = {k: v for k, v in raw[2].items() if k != "published_at"}
        summary = _ingest(_payload(raw, run_id="run-mixed"), store)
        ledger = store.audit_admissions(run_id=summary["run_id"])
        outcomes = {row.item_id: row.outcome for row in ledger}
        # accepted / rejected / failed: exactly one row per item
        assert sorted(outcomes.values()) == ["accepted", "failed", "rejected"]
        assert summary["ledger"] == {"accepted": 1, "rejected": 1, "failed": 1}
        assert len(ledger) == len(raw)
        # failed row carries the registered mapper reason code
        failed = [r for r in ledger if r.outcome == "failed"][0]
        assert "MAP_FAILED" in failed.reason_codes

    def test_partial_fetch_payload_is_recorded_as_partial_failure(self, store):
        summary = _ingest(
            _payload([_raw_item(1)], fetch_status="partial_failure"), store
        )
        assert summary["status"] == "partial_failure"
        assert store.get_run(RUN_ID).status == "partial_failure"

    def test_partial_enrichment_payload_is_recorded_as_partial_failure(self, store):
        summary = _ingest(
            _payload(
                [_raw_item(1)],
                enrich_result={"status": "partial", "error_code": "HZ_INTERNAL_ERROR"},
            ),
            store,
        )
        assert summary["status"] == "partial_failure"
        assert store.get_run(RUN_ID).status == "partial_failure"


class TestIdempotentReplay:
    def test_same_run_twice_is_pure_noop(self, store):
        payload = _payload([_raw_item(1)])
        first = _ingest(payload, store)
        second = _ingest(payload, store)
        assert store.stats().item_count == 1
        # Ledger stays append-only: still exactly one accepted row for the run.
        rows = store.audit_admissions(run_id=first["run_id"])
        accepted_rows = [r for r in rows if r.outcome == "accepted"]
        assert len(accepted_rows) == 1
        assert second["replayed"] is True
        assert second["ledger"].get("accepted", 0) == 1  # replay decided, not re-inserted

    def test_same_story_in_new_run_is_duplicate_not_repersisted(self, store):
        first = _ingest(_payload([_raw_item(1)], run_id="run-first"), store)
        second = _ingest(_payload([_raw_item(1)], run_id="run-second"), store)
        assert second["run_id"] != first["run_id"]
        assert store.stats().item_count == 1
        rows = store.audit_admissions(run_id=second["run_id"])
        assert rows[0].outcome == "rejected"
        assert rows[0].reason_codes[0] in ("DUPLICATE_ID", "DUPLICATE_URL")


class TestEmptyPayload:
    def test_empty_payload_is_explicit_and_persists_nothing(self, store):
        # An empty fetch is a recorded, successful run with zero counts.
        summary = _ingest(_payload([], stage="raw"), store)
        assert summary["status"] == "empty"
        assert summary["counts"]["fetched"] == 0
        assert summary["counts"]["persisted"] == 0
        assert store.stats().item_count == 0

    def test_payload_with_no_persisted_stages_ingests_nothing(self, store):
        summary = _ingest(
            {
                "run_id": "run-nostages",
                "radar_ref": PIN,
                "stages_present": [],
                "stage_payloads": {},
                "fetch_status": "success",
                "enrich_result": None,
            },
            store,
        )
        assert summary["status"] == "empty"
        assert store.stats().item_count == 0


class TestRadarRefProvenance:
    """Run identity comes from the producer, never from a local constant.

    Only the collection side knows which pinned provider checkout produced a
    run, so the payload must state it. A guessed fallback would silently
    attribute the run to the wrong revision.
    """

    def test_payload_ref_is_recorded_verbatim(self, store):
        summary = _ingest(
            _payload([_raw_item(1)], radar_ref="deadbeefcafe"), store
        )
        assert summary["radar_ref"] == "deadbeefcafe"
        assert store.get_run(RUN_ID).radar_ref == "deadbeefcafe"

    def test_ref_is_not_replaced_by_a_local_default(self, store):
        _ingest(_payload([_raw_item(1)], radar_ref="other-pin"), store)
        recorded = store.get_run(RUN_ID).radar_ref
        assert recorded == "other-pin"
        assert recorded != PIN

    @pytest.mark.parametrize("missing", [None, "", "   "])
    def test_missing_or_blank_ref_is_refused(self, store, missing):
        payload = _payload([_raw_item(1)])
        if missing is None:
            del payload["radar_ref"]
        else:
            payload["radar_ref"] = missing
        with pytest.raises(ValueError, match="radar_ref"):
            _ingest(payload, store)
        # Refused before any accounting is written: no half-recorded run.
        assert store.get_run(RUN_ID) is None
        assert store.stats().item_count == 0

    def test_non_string_ref_is_refused(self, store):
        with pytest.raises(ValueError, match="radar_ref"):
            _ingest(_payload([_raw_item(1)], radar_ref=596), store)
        assert store.get_run(RUN_ID) is None

    def test_replay_reports_the_recorded_ref(self, store):
        first = _ingest(_payload([_raw_item(1)], radar_ref="pinned-a"), store)
        second = _ingest(_payload([_raw_item(1)], radar_ref="pinned-b"), store)
        assert first["radar_ref"] == "pinned-a"
        # Replay is a no-op, so the originally recorded reference stands.
        assert second["replayed"] is True
        assert second["radar_ref"] == "pinned-a"


class TestIdentityTracing:
    def test_one_id_traced_through_accepted_rejected_retrieved(self, store):
        """G1/G2: one minted ID survives accept, duplicate rejection, retrieval."""
        first = _ingest(_payload([_raw_item(1)], run_id="run-first"), store)
        asset_id = "horizon:github:acme:repo-1"
        # accepted then retrievable by that exact ID
        assert store.get_item(asset_id) is not None
        # same story again → rejected against the SAME id, with a pointer
        second = _ingest(_payload([_raw_item(1)], run_id="run-second"), store)
        assert second["run_id"] != first["run_id"]
        rows = store.audit_admissions(run_id=second["run_id"])
        assert rows[0].item_id == asset_id
        assert rows[0].outcome == "rejected"
        assert rows[0].duplicate_of == asset_id
        # audit ledger for the original run still traces acceptance
        first_rows = store.audit_admissions(run_id=first["run_id"], outcome="accepted")
        assert [r.item_id for r in first_rows] == [asset_id]
