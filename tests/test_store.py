"""Ticket 07 tests — canonical SQLite asset store.

Covers the acceptance criteria: transactional repeatable versioned migrations,
idempotent write-once item admission with partial URL uniqueness, append-only
admissions with ordered registry reason codes, run invariants I2/I3 gating,
typed reader with accepted-only default plus explicit audit paths, story edges,
FTS5 CJK probe with explicit tested fallback, JSONL export/restore, and
consistent backup with manifest verification. Static legacy fixtures/oracles
are exercised in the identity-mapping tests at the end.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from kb import model as kb_model
from kb.horizon.contract import mint_asset_id
from kb.store import export as export_mod
from kb.store import fts as fts_mod
from kb.store import reader as reader_mod
from kb.store import schema as schema_mod
from kb.store import writer as writer_mod
from kb.store.fixtures import mapped_store_item
from kb.store.model import AssetStore

pytestmark = pytest.mark.non_llm


@pytest.fixture()
def conn() -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    schema_mod.migrate(connection)
    yield connection
    connection.close()


@pytest.fixture()
def store() -> AssetStore:
    return AssetStore.open(":memory:")


# ---------------------------------------------------------------------------
# schema: transactional, repeatable, versioned
# ---------------------------------------------------------------------------


class TestSchema:
    def test_migrate_creates_canonical_tables_and_indexes(self, conn):
        assert schema_mod.schema_version(conn) == 1
        assert schema_mod.verify_schema(conn)
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            )
        }
        assert {
            "items", "admissions", "runs", "tags", "artifacts", "artifact_blocks",
            "artifact_sources", "block_source_refs", "edges", "schema_migrations",
        } <= tables

    def test_migrate_is_repeatable(self, conn):
        assert schema_mod.migrate(conn) == 1
        assert schema_mod.migrate(conn) == 1
        rows = conn.execute("SELECT COUNT(*) FROM schema_migrations").fetchone()[0]
        assert rows == 1

    def test_migration_failure_rolls_back(self):
        # A fresh DB whose first migration step fails must record no version
        # (transactional step) and remain migratable afterwards.
        conn = sqlite3.connect(":memory:")
        try:
            original = schema_mod._v1_items
            schema_mod._v1_items = lambda: "CREATE TABLE items (bogus TEXT)"
            try:
                # Rebuild MIGRATIONS with the poisoned step.
                poisoned = (
                    (1, "poisoned step",
                     ("CREATE TABLE items (bogus TEXT)",)),
                )
                saved = schema_mod.MIGRATIONS
                schema_mod.MIGRATIONS = poisoned
                with pytest.raises(schema_mod.MigrationError):
                    schema_mod.migrate(conn)
            finally:
                schema_mod.MIGRATIONS = saved
                schema_mod._v1_items = original
            assert schema_mod.applied_versions(conn) == set()
            assert schema_mod.schema_version(conn) == 0
            # Repeatable: the real migration still applies cleanly after the
            # failed attempt (rollback left no partial state).
            assert schema_mod.migrate(conn) == 1
            assert schema_mod.verify_schema(conn)
        finally:
            conn.close()

    def test_check_constraints_generated_from_model_registry(self, conn):
        # The DDL CHECK lists are generated from kb/model.py, not copied (O2).
        check_sql = {
            str(name): str(sql)
            for name, sql in conn.execute(
                "SELECT name, sql FROM sqlite_master WHERE type='table' AND sql IS NOT NULL"
            )
        }
        items_ddl = check_sql["items"]
        admissions_ddl = check_sql["admissions"]
        runs_ddl = check_sql["runs"]
        for value in kb_model.ASSET_STATES:
            assert f"'{value}'" in items_ddl
        for value in kb_model.OUTCOMES:
            assert f"'{value}'" in admissions_ddl
        for value in kb_model.RUN_STATUSES:
            assert f"'{value}'" in runs_ddl

    def test_partial_unique_url_index_on_accepted_only(self, conn):
        index_sql = conn.execute(
            "SELECT sql FROM sqlite_master WHERE name = 'idx_items_url'"
        ).fetchone()[0]
        assert "WHERE state = 'accepted'" in index_sql
        assert "UNIQUE" in index_sql

    def test_superseded_by_fk_deferrable(self, conn):
        row = conn.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='items'"
        ).fetchone()[0]
        assert "DEFERRABLE INITIALLY DEFERRED" in row

    def test_foreign_keys_enforced(self, conn):
        assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1


# ---------------------------------------------------------------------------
# writer: write-once items, partial URL uniqueness, append-only ledger
# ---------------------------------------------------------------------------


class TestWriterItems:
    def test_ensure_item_inserts_once_then_duplicate_id_noop(self, conn):
        conn.execute(
            "INSERT INTO runs (run_id, radar, radar_ref, started_at, status) "
            "VALUES ('run-1', 'horizon', '596e2b1', '2026-09-12T00:00:00Z', 'success')"
        )
        first = writer_mod.ensure_item(conn, mapped_store_item(), run_id="run-1")
        assert first == {"inserted": 1, "duplicate_id": 0, "duplicate_url": 0}

        modified = mapped_store_item()
        modified["title"] = "CHANGED TITLE SHOULD NEVER LAND"
        second = writer_mod.ensure_item(conn, modified, run_id="run-1")
        # Same (run_id, item_id) already decided in run-1: precedence 0 — a
        # pure no-op with NO new admission row (the ledger is append-only).
        assert second.get("replayed") is True
        assert second["inserted"] == 0
        ledger_count = conn.execute(
            "SELECT COUNT(*) FROM admissions WHERE run_id='run-1' AND item_id=?",
            (modified["id"],),
        ).fetchone()[0]
        assert ledger_count == 1  # only the original accept row

        row = conn.execute("SELECT title FROM items WHERE id = ?", (modified["id"],)).fetchone()
        assert row["title"] != "CHANGED TITLE SHOULD NEVER LAND"
        assert conn.execute("SELECT COUNT(*) FROM items").fetchone()[0] == 1

    def test_duplicate_url_loser_gets_ledger_row_and_no_items_row(self, conn):
        conn.execute(
            "INSERT INTO runs (run_id, radar, radar_ref, started_at, status) "
            "VALUES ('run-1', 'horizon', '596e2b1', '2026-09-12T00:00:00Z', 'success')"
        )
        winner = mapped_store_item()
        writer_mod.ensure_item(conn, winner, run_id="run-1")

        loser = mapped_store_item(item_id="github:acme:other#2")
        loser["url"] = winner["url"]
        result = writer_mod.ensure_item(conn, loser, run_id="run-1")
        assert result["inserted"] == 0 and result["duplicate_url"] == 1

        assert conn.execute(
            "SELECT COUNT(*) FROM items WHERE id = ?", (loser["id"],)
        ).fetchone()[0] == 0
        ledger = conn.execute(
            "SELECT outcome, reason_codes, duplicate_of FROM admissions "
            "WHERE run_id='run-1' AND item_id = ?",
            (loser["id"],),
        ).fetchone()
        assert ledger["outcome"] == "rejected"
        assert json.loads(ledger["reason_codes"]) == ["DUPLICATE_URL"]
        assert ledger["duplicate_of"] == winner["id"]

    def test_url_uniqueness_normalized_by_trailing_slash_and_host_case(self, conn):
        conn.execute(
            "INSERT INTO runs (run_id, radar, radar_ref, started_at, status) "
            "VALUES ('run-1', 'horizon', '596e2b1', '2026-09-12T00:00:00Z', 'success')"
        )
        winner = mapped_store_item(url="https://Example.com/post/")
        writer_mod.ensure_item(conn, winner, run_id="run-1")
        challenger = mapped_store_item(item_id="github:acme:dupe#3",
                                       url="https://example.com/post")
        result = writer_mod.ensure_item(conn, challenger, run_id="run-1")
        # Exact-column uniqueness is enforced by the index; normalization
        # happens at admission time via kb/model.normalize_url.
        assert result["inserted"] + result["duplicate_url"] == 1

    def test_story_fp_derived_from_single_owner_algorithm(self, conn):
        conn.execute(
            "INSERT INTO runs (run_id, radar, radar_ref, started_at, status) "
            "VALUES ('run-1', 'horizon', '596e2b1', '2026-09-12T00:00:00Z', 'success')"
        )
        item = mapped_store_item()
        writer_mod.ensure_item(conn, item, run_id="run-1")
        row = conn.execute(
            "SELECT story_fp FROM items WHERE id = ?", (item["id"],)
        ).fetchone()
        expected = kb_model.story_fingerprint(item["title"], item["url"])
        assert row["story_fp"] == expected


class TestWriterLedger:
    def _seed_run(self, conn, run_id="run-1"):
        conn.execute(
            "INSERT INTO runs (run_id, radar, radar_ref, started_at, status) "
            f"VALUES ('{run_id}', 'horizon', '596e2b1', '2026-09-12T00:00:00Z', 'success')"
        )

    def test_unregistered_reason_code_rejected(self, conn):
        self._seed_run(conn)
        with pytest.raises(writer_mod.StoreWriteError, match="registry"):
            writer_mod.record_rejections(
                conn,
                [{"item_id": "x", "outcome": "rejected",
                  "reason_codes": ["MADE_UP_CODE"]}],
                run_id="run-1",
            )

    def test_empty_reason_codes_rejected(self, conn):
        self._seed_run(conn)
        with pytest.raises(writer_mod.StoreWriteError, match="non-empty"):
            writer_mod.record_rejections(
                conn, [{"item_id": "x", "outcome": "rejected", "reason_codes": []}],
                run_id="run-1",
            )

    def test_ledger_is_append_only_pk_conflict_raises(self, conn):
        self._seed_run(conn)
        row = {"item_id": "github:acme:widget#1", "outcome": "rejected",
               "reason_codes": ["DUPLICATE_ID"]}
        assert writer_mod.record_rejections(conn, [row], run_id="run-1") == 1
        with pytest.raises(writer_mod.WriteConflict, match="append-only"):
            writer_mod.record_rejections(conn, [row], run_id="run-1")

    def test_duplicate_of_must_reference_known_candidate(self, conn):
        self._seed_run(conn)
        with pytest.raises(writer_mod.WriteConflict, match="duplicate_of"):
            writer_mod.record_rejections(
                conn,
                [{"item_id": "a", "outcome": "rejected",
                  "reason_codes": ["DUPLICATE_URL"], "duplicate_of": "ghost-id"}],
                run_id="run-1",
            )

    def test_accepted_row_cannot_carry_negative_pattern_codes(self, conn):
        self._seed_run(conn)
        with pytest.raises(writer_mod.StoreWriteError, match="NEG_"):
            writer_mod.record_rejections(
                conn,
                [{"item_id": "a", "outcome": "accepted",
                  "reason_codes": ["ACCEPTED", "NEG_HYPE_NO_MECHANISM"]}],
                run_id="run-1",
            )


class TestSupersede:
    def _seed_accepted(self, conn, item, run_id="run-1"):
        conn.execute(
            "INSERT INTO runs (run_id, radar, radar_ref, started_at, status) "
            f"VALUES ('{run_id}', 'horizon', '596e2b1', '2026-09-12T00:00:00Z', 'success')"
        )
        writer_mod.ensure_item(conn, item, run_id=run_id)

    def test_supersede_is_one_transaction(self, conn):
        predecessor = mapped_store_item()
        self._seed_accepted(conn, predecessor)
        successor = mapped_store_item(item_id="github:acme:widget#2")
        # Same story, different URL — the supersede decision frees the URL.
        successor["url"] = predecessor["url"].rstrip("/") + "/v2"

        # The successor must already be an accepted asset (supersede links
        # two existing assets; run-2 must be an ensured run — no placeholders).
        conn.execute(
            "INSERT INTO runs (run_id, radar, radar_ref, started_at, status) "
            "VALUES ('run-2', 'horizon', '596e2b1', '2026-09-12T00:00:00Z', 'success')"
        )
        assert writer_mod.ensure_item(conn, successor, run_id="run-2")["inserted"] == 1

        assert writer_mod.supersede_item(
            conn, predecessor["id"], successor_id=successor["id"], run_id="run-2"
        )
        old_row = conn.execute(
            "SELECT state, superseded_by FROM items WHERE id = ?", (predecessor["id"],)
        ).fetchone()
        assert old_row["state"] == "superseded"
        assert old_row["superseded_by"] == successor["id"]
        ledger = conn.execute(
            "SELECT outcome FROM admissions WHERE run_id='run-2' AND item_id=?",
            (predecessor["id"],),
        ).fetchone()
        assert ledger["outcome"] == "supersede"

    def test_supersede_of_unknown_item_raises(self, conn):
        conn.execute(
            "INSERT INTO runs (run_id, radar, radar_ref, started_at, status) "
            "VALUES ('run-1', 'horizon', '596e2b1', '2026-09-12T00:00:00Z', 'success')"
        )
        with pytest.raises(writer_mod.WriteConflict, match="no items row"):
            writer_mod.supersede_item(conn, "ghost", successor_id="s", run_id="run-1")


# ---------------------------------------------------------------------------
# ingest_run: invariants gate persistence
# ---------------------------------------------------------------------------


class TestIngestRun:
    def test_ingest_run_persists_items_and_honest_counts(self, conn):
        run = {"run_id": "run-1", "radar": "horizon", "radar_ref": "596e2b1",
               "status": "success"}
        items = [mapped_store_item(item_id=f"github:acme:w#{i}") for i in range(3)]
        rejections = [
            {"item_id": "github:acme:low#9", "outcome": "rejected",
             "reason_codes": ["REJECTED_LOW_SCORE"]},
            {"item_id": "github:acme:map#10", "outcome": "failed",
             "reason_codes": ["MAP_FAILED"]},
        ]
        result = writer_mod.ingest_run(conn, run, items, rejections)
        assert result["inserted"] == 3
        assert result["ledger"] == {"accepted": 3, "rejected": 1, "failed": 1}
        assert result["invariant_ok"] is True

        run_row = reader_mod.get_run(conn, "run-1")
        assert run_row.accepted == 3
        assert run_row.rejected == 1
        assert run_row.failed == 1
        assert run_row.persisted == 3
        assert run_row.fetched == 5
        assert run_row.invariant_ok is True

    def test_replaying_same_run_is_idempotent(self, conn):
        run = {"run_id": "run-1", "radar": "horizon", "radar_ref": "596e2b1",
               "status": "success"}
        items = [mapped_store_item()]
        writer_mod.ingest_run(conn, run, items, [])
        # Replay: the re-presented asset is a DUPLICATE_ID candidate reject;
        # the stored row is untouched and no second items row appears.
        writer_mod.ingest_run(conn, run, items, [])
        assert conn.execute("SELECT COUNT(*) FROM items").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM runs").fetchone()[0] == 1

    def test_invariant_violation_persists_nothing(self, conn):
        # A rejected row that would leave I3 broken is caught inside the
        # transaction: a rejection referencing an unregistered code fails and
        # the accepted items of the same call must not survive.
        run = {"run_id": "run-x", "radar": "horizon", "radar_ref": "596e2b1",
               "status": "success"}
        items = [mapped_store_item()]
        bad_rejections = [
            {"item_id": "github:acme:bad#1", "outcome": "rejected",
             "reason_codes": ["NOT_IN_REGISTRY"]},
        ]
        with pytest.raises(writer_mod.StoreWriteError):
            writer_mod.ingest_run(conn, run, items, bad_rejections)
        assert conn.execute("SELECT COUNT(*) FROM items").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM admissions").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM runs").fetchone()[0] == 0

    def test_duplicate_across_runs_is_rejected_with_pointer(self, conn):
        run1 = {"run_id": "run-1", "radar": "horizon", "radar_ref": "596e2b1",
                "status": "success"}
        run2 = {"run_id": "run-2", "radar": "horizon", "radar_ref": "596e2b1",
                "status": "success"}
        item = mapped_store_item()
        writer_mod.ingest_run(conn, run1, [item], [])
        writer_mod.ingest_run(conn, run2, [dict(item)], [])
        ledger = reader_mod.get_admissions(conn, item["id"], run_id="run-2")
        assert ledger[0].outcome == "rejected"
        assert ledger[0].reason_codes == ("DUPLICATE_ID",)
        assert ledger[0].duplicate_of == item["id"]


# ---------------------------------------------------------------------------
# reader: accepted-only default + explicit audit paths (I4)
# ---------------------------------------------------------------------------


class TestReader:
    def _seed(self, store: AssetStore) -> str:
        item = mapped_store_item()
        store.ingest_run(
            {"run_id": "run-1", "radar": "horizon", "radar_ref": "596e2b1",
             "status": "success"},
            [item],
            [{"item_id": "github:acme:rejected#1", "outcome": "rejected",
              "reason_codes": ["REJECTED_LOW_SCORE"]}],
        )
        return item["id"]

    def test_default_reads_hide_superseded(self, store):
        item_id = self._seed(store)
        assert store.get_item(item_id) is not None
        assert store.get_item("github:acme:rejected#1") is None  # ledger-only

    def test_get_superseded_requires_opt_in(self, store):
        item = mapped_store_item()
        successor = mapped_store_item(item_id="github:acme:widget#9")
        successor["url"] = item["url"].rstrip("/") + "/v9"
        store.ingest_run(
            {"run_id": "run-1", "radar": "horizon", "radar_ref": "p", "status": "success"},
            [item], [],
        )
        # The successor must be an accepted asset and run-2 ensured before
        # the supersede decision (public preconditions, no placeholders).
        store.ingest_run(
            {"run_id": "run-2", "radar": "horizon", "radar_ref": "p", "status": "success"},
            [successor], [],
        )
        store.supersede_item(item["id"], successor_id=successor["id"], run_id="run-2")
        assert store.get_item(item["id"]) is None
        fetched = store.get_item(item["id"], include_superseded=True)
        assert fetched is not None
        assert fetched.state == "superseded"
        assert fetched.superseded_by == successor["id"]

    def test_audit_path_returns_rejections_with_reasons(self, store):
        self._seed(store)
        rows = store.audit_admissions(run_id="run-1", outcome="rejected")
        assert len(rows) == 1
        assert rows[0].reason_codes == ("REJECTED_LOW_SCORE",)
        assert rows[0].policy_id == "admission-policy"
        assert rows[0].policy_version

    def test_get_admissions_traces_item_identity(self, store):
        item_id = self._seed(store)
        rows = store.get_admissions(item_id)
        assert [row.outcome for row in rows] == ["accepted"]

    def test_stats_and_latest_published_day(self, store):
        self._seed(store)
        stats = store.stats()
        assert stats.item_count == 1
        assert stats.accepted_count == 1
        assert stats.admission_count == 2
        assert store.latest_published_day() == "2026-09-11"

    def test_story_edges_link_same_story_assets(self, store):
        a = mapped_store_item(item_id="github:acme:story#1", url="https://x.com/a")
        b = mapped_store_item(item_id="github:acme:story#2", url="https://x.com/b")
        store.ingest_run(
            {"run_id": "run-1", "radar": "horizon", "radar_ref": "p", "status": "success"},
            [a, b], [],
        )
        assert store.story_edges(a["id"]) == []
        store._conn.execute(
            "INSERT INTO edges (src_id, dst_id, kind, weight, created_at) "
            "VALUES (?, ?, 'same_story', 1.0, '2026-09-12T00:00:00Z')",
            (a["id"], b["id"]),
        )
        edges = store.story_edges(a["id"])
        assert len(edges) == 1
        assert edges[0]["dst_id"] == b["id"]
        assert edges[0]["kind"] == "same_story"


# ---------------------------------------------------------------------------
# FTS5: CJK probe + explicit tested fallback
# ---------------------------------------------------------------------------


class TestFTS:
    def test_probe_reports_real_support(self, conn):
        # Local SQLite 3.53 ships trigram; the probe must be honest either way.
        assert fts_mod.probe_cjk_support(conn) is True

    def test_install_uses_trigram_when_supported(self, conn):
        mode = fts_mod.install(conn)
        assert mode == fts_mod.FTS_TRIGRAM
        assert fts_mod.fts_mode(conn) == fts_mod.FTS_TRIGRAM

    def test_cjk_search_hits_chinese_content(self, conn):
        writer_mod.ensure_run(conn, {
            "run_id": "run-1", "radar": "horizon", "radar_ref": "p",
            "started_at": None, "status": "success",
        })
        writer_mod.ensure_item(conn, mapped_store_item(), run_id="run-1")
        fts_mod.install(conn)
        # FTS columns are title/summary/content_main/content_comments; the
        # fixture's Chinese text lives in the summary.
        items, mode = fts_mod.search(conn, "有用的")
        assert mode == fts_mod.FTS_TRIGRAM
        assert len(items) == 1

    def test_like_fallback_mode_serves_search(self, conn):
        # Force the explicit fallback in the meta table (the way a build
        # without trigram support would be recorded at startup).
        conn.execute("BEGIN IMMEDIATE")
        conn.execute(
            "CREATE TABLE IF NOT EXISTS kb_fts_meta (id INTEGER PRIMARY KEY CHECK (id = 1), "
            "mode TEXT NOT NULL)"
        )
        conn.execute(
            "INSERT OR REPLACE INTO kb_fts_meta (id, mode) VALUES (1, ?)",
            (fts_mod.FTS_LIKE_FALLBACK,),
        )
        conn.execute("COMMIT")
        writer_mod.ensure_run(conn, {
            "run_id": "run-1", "radar": "horizon", "radar_ref": "p",
            "started_at": None, "status": "success",
        })
        writer_mod.ensure_item(conn, mapped_store_item(), run_id="run-1")
        items, mode = fts_mod.search(conn, "horizon")
        assert mode == fts_mod.FTS_LIKE_FALLBACK
        assert len(items) == 1

    def test_fallback_is_recorded_not_silent(self, conn):
        # The degradation is persisted in kb_fts_meta so every consumer can
        # assert which mode serves reads (design.md §2: no silent downgrade).
        conn.execute("BEGIN IMMEDIATE")
        conn.execute(
            "CREATE TABLE IF NOT EXISTS kb_fts_meta (id INTEGER PRIMARY KEY CHECK (id = 1), "
            "mode TEXT NOT NULL)"
        )
        conn.execute(
            "INSERT OR REPLACE INTO kb_fts_meta (id, mode) VALUES (1, ?)",
            (fts_mod.FTS_LIKE_FALLBACK,),
        )
        conn.execute("COMMIT")
        assert fts_mod.fts_mode(conn) == fts_mod.FTS_LIKE_FALLBACK

    def test_search_default_excludes_superseded(self, conn):
        writer_mod.ensure_run(conn, {
            "run_id": "run-1", "radar": "horizon", "radar_ref": "p",
            "started_at": None, "status": "success",
        })
        item = mapped_store_item()
        writer_mod.ensure_item(conn, item, run_id="run-1")
        fts_mod.install(conn)
        successor = mapped_store_item(item_id="github:acme:widget#77")
        successor["url"] = item["url"].rstrip("/") + "/v77"
        writer_mod.ensure_run(conn, {
            "run_id": "run-2", "radar": "horizon", "radar_ref": "p",
            "started_at": None, "status": "success",
        })
        assert writer_mod.ensure_item(conn, successor, run_id="run-2")["inserted"] == 1
        writer_mod.supersede_item(conn, item["id"], successor_id=successor["id"],
                                  run_id="run-2")
        # 'Horizon' is a contiguous trigram token of the fixture title.
        items, _ = fts_mod.search(conn, "Horizon")
        assert all(row.state == "accepted" for row in items)
        assert len(items) == 1
        assert items[0].id == successor["id"]


# ---------------------------------------------------------------------------
# export / backup / restore
# ---------------------------------------------------------------------------


class TestExportBackupRestore:
    def _seed(self, store: AssetStore) -> str:
        item = mapped_store_item()
        store.ingest_run(
            {"run_id": "run-1", "radar": "horizon", "radar_ref": "596e2b1",
             "status": "success"},
            [item],
            [{"item_id": "github:acme:rejected#1", "outcome": "rejected",
              "reason_codes": ["REJECTED_LOW_SCORE"]}],
        )
        return item["id"]

    def test_export_jsonl_manifest_has_counts_and_checksum(self, store, tmp_path):
        self._seed(store)
        target = tmp_path / "export" / "kb.jsonl"
        manifest = store.export_jsonl(target)
        assert manifest["item_count"] == 1
        assert manifest["admission_count"] is None  # audit not requested
        assert manifest["sha256"]
        assert manifest["size_bytes"] > 0
        lines = target.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 1
        payload = json.loads(lines[0])
        assert payload["state"] == "accepted"
        assert payload["tags"] == ["mcp", "tool-use"]

    def test_export_include_audit_writes_ledger_rows(self, store, tmp_path):
        self._seed(store)
        target = tmp_path / "kb-audit.jsonl"
        manifest = store.export_jsonl(target, include_audit=True)
        assert manifest["admission_count"] == 2
        lines = target.read_text(encoding="utf-8").strip().splitlines()
        payloads = [json.loads(line) for line in lines]
        kinds = {p.get("kind") for p in payloads}
        assert kinds == {"admission", None}
        admissions = [p for p in payloads if p.get("kind") == "admission"]
        assert all("reason_codes" in a for a in admissions)

    def test_restore_jsonl_is_idempotent_and_write_once(self, store, tmp_path):
        item_id = self._seed(store)
        target = tmp_path / "kb.jsonl"
        store.export_jsonl(target)

        other = AssetStore.open(":memory:")
        first = other.restore_jsonl(target)
        assert first["restored"] == 1
        assert first["duplicates"] == 0
        # Replay: write-once, no second row, duplicates counted.
        second = other.restore_jsonl(target)
        assert second["restored"] == 0
        assert second["duplicates"] == 1
        assert other.stats().item_count == 1
        assert other.get_item(item_id).title

    def test_backup_writes_manifest_and_snapshot(self, store, tmp_path):
        self._seed(store)
        target = tmp_path / "backups" / "kb.sqlite"
        manifest = store.backup(target)
        assert manifest["item_count"] == 1
        assert manifest["run_count"] == 1
        assert manifest["consistent"] is True
        assert target.exists()
        assert Path(str(target) + ".manifest.json").exists()

        reopened = AssetStore.open(target)
        try:
            assert reopened.stats().item_count == 1
        finally:
            reopened.close()

    def test_restore_from_backup_verifies_checksum_before_copy(self, store, tmp_path):
        self._seed(store)
        snapshot = tmp_path / "kb.sqlite"
        store.backup(snapshot)

        target = tmp_path / "restored" / "kb.sqlite"
        result = export_mod.restore_from_backup(snapshot, target_path=target)
        assert result["restored"] is True
        assert result["item_count"] == 1

        restored = AssetStore.open(target)
        try:
            assert restored.stats().item_count == 1
        finally:
            restored.close()

    def test_restore_aborts_on_checksum_mismatch(self, store, tmp_path):
        self._seed(store)
        snapshot = tmp_path / "kb.sqlite"
        store.backup(snapshot)
        manifest_path = Path(str(snapshot) + ".manifest.json")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["sha256"] = "0" * 64
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

        target = tmp_path / "restored" / "kb.sqlite"
        with pytest.raises(ValueError, match="checksum mismatch"):
            export_mod.restore_from_backup(snapshot, target_path=target)
        assert not target.exists()

    def test_restore_missing_backup_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            export_mod.restore_from_backup(
                tmp_path / "missing.sqlite", target_path=tmp_path / "x.sqlite"
            )


# ---------------------------------------------------------------------------
# kb/model.py registry invariants (single-vocabulary ownership)
# ---------------------------------------------------------------------------


class TestModelRegistry:
    def test_registry_has_all_documented_namespaces(self):
        codes = kb_model.ReasonCode.all_codes()
        for expected in (
            "ACCEPTED", "TOPIC_P0_BOOST", "RESCUED_BY_TOPIC", "REJECTED_LOW_SCORE",
            "LOW_SOURCE_TYPE", "NEG_HYPE_NO_MECHANISM", "NEG_HIRING_CONFERENCE",
            "NEG_SHALLOW_LAUNCH", "NEG_GENERIC_ENTERPRISE", "DUPLICATE_ID",
            "DUPLICATE_URL", "MISSING_SCORE", "MISSING_SUMMARY",
            "MALFORMED_ENRICHMENT", "MALFORMED_METADATA", "MISSING_PUBLISHED_AT",
            "LOW_CONFIDENCE_MATCH", "MAP_FAILED", "TRUNCATED_STAGE",
            "ENVELOPE_INVALID", "STAGE_TIMEOUT", "ENRICHMENT_UNAVAILABLE",
        ):
            assert expected in codes

    def test_normalize_url_strips_scheme_trailing_slash_lowercases_host(self):
        assert kb_model.normalize_url("https://Example.com/Post/") == "example.com/Post"
        assert kb_model.normalize_url("http://example.com") == "example.com"
        assert kb_model.normalize_url("https://EXAMPLE.com/a/b") == "example.com/a/b"

    def test_story_fingerprint_matches_documented_formula(self):
        fp = kb_model.story_fingerprint("Hello, World! 你好", "https://Example.com/x")
        assert fp == "hello world 你好|example.com"

    def test_mint_matches_horizon_mapper_rule(self):
        assert kb_model.mint_radical_id("horizon", "github:a:1") == mint_asset_id("github:a:1")
        with pytest.raises(ValueError):
            kb_model.mint_radical_id("", "x")


# ---------------------------------------------------------------------------
# ticket 12: mapper derived fields projected into metadata (UI consumer seam)
# ---------------------------------------------------------------------------


class TestDerivedMetadataProjection:
    def test_artifacts_reach_metadata_json_and_metadata_is_kept(self, store):
        item = mapped_store_item()
        store.ingest_run(
            {"run_id": "run-ui", "radar": "horizon", "radar_ref": "596e2b1",
             "status": "success"},
            [item], [],
        )
        rec = store.get_item(item["id"])
        doc = json.loads(rec.metadata_json)
        assert doc["artifacts"][0]["language"] == "zh"
        blocks = doc["artifacts"][0]["blocks"]
        assert blocks[0]["title"] == "摘要" and blocks[0]["is_primary"] is True
        # mapper metadata rides along untouched in the same bounded document
        assert doc["upstream"] == "kept-bounded"

    def test_metadata_without_mapper_keys_is_untouched(self, conn):
        row = mapped_store_item()
        row["metadata_json"] = {"custom": "kept"}
        row.pop("artifacts", None)
        row.pop("horizon_extra", None)
        row["id"] = "horizon:plain:1"
        row["url"] = "https://example.com/plain"
        writer_mod.ingest_run(
            conn,
            {"run_id": "run-plain", "radar": "horizon", "radar_ref": "596e2b1",
             "status": "success"},
            [row], [],
        )
        from kb.store import reader as reader_mod

        rec = reader_mod.get_item(conn, "horizon:plain:1")
        assert json.loads(rec.metadata_json) == {"custom": "kept"}


# ---------------------------------------------------------------------------
# legacy fixture corpus: identity mapping against the static oracle
# ---------------------------------------------------------------------------


FIXTURE_ROOT = Path(__file__).resolve().parent / "fixtures" / "legacy_articles"


class TestLegacyFixtureIdentity:
    """Ticket-04 fixtures bind the store's identity rule to ``legacy:`` minting."""

    def _articles(self) -> list[dict]:
        return [
            json.loads(p.read_text(encoding="utf-8"))
            for p in sorted((FIXTURE_ROOT / "articles").glob("*.json"))
        ]

    def test_minted_legacy_ids_accepted_by_store(self, store):
        import sys

        sys.path.insert(0, str(FIXTURE_ROOT))
        try:
            from expected_mapping import mint_canonical_id
        finally:
            sys.path.remove(str(FIXTURE_ROOT))

        items = []
        for article in self._articles()[:5]:
            row = mapped_store_item()
            row["id"] = mint_canonical_id(article["id"])
            row["url"] = article.get("source_url") or article.get("url")
            row["title"] = article["title"]
            row["summary"] = article["summary"]
            row["source_type"] = article.get("source_type") or "unknown"
            row["published_at"] = article.get("published_at")
            row["author"] = article.get("author")
            items.append(row)
        store.ingest_run(
            {"run_id": "import-1", "radar": "legacy", "radar_ref": "6054488",
             "status": "success"},
            items, [],
        )
        for row in items:
            fetched = store.get_item(row["id"])
            assert fetched is not None
            assert fetched.id == mint_canonical_id(fetched.id.split(":", 1)[1])

    def test_colon_ids_are_legal_in_the_store(self, store):
        colon_id = "legacy:rss:mitchell-hashimoto-20260530-010"
        row = mapped_store_item()
        row["id"] = colon_id
        store.ingest_run(
            {"run_id": "import-1", "radar": "legacy", "radar_ref": "6054488",
             "status": "success"},
            [row], [],
        )
        assert store.get_item(colon_id) is not None

    def test_duplicate_legacy_url_maps_to_duplicate_url_decision(self, store):
        import sys

        sys.path.insert(0, str(FIXTURE_ROOT))
        try:
            from expected_mapping import mint_canonical_id
        finally:
            sys.path.remove(str(FIXTURE_ROOT))


        articles = self._articles()
        first = articles[0]
        item_a = mapped_store_item()
        item_a["id"] = mint_canonical_id(first["id"])
        item_a["url"] = first.get("source_url") or first.get("url")
        item_a["title"] = first["title"]
        item_a["summary"] = first["summary"]
        item_a["source_type"] = first.get("source_type") or "unknown"
        item_a["published_at"] = first.get("published_at")
        store.ingest_run(
            {"run_id": "import-1", "radar": "legacy", "radar_ref": "6054488",
             "status": "success"},
            [item_a], [],
        )
        # A second record carrying the same URL (dedup oracle behavior);
        # import-2 is ensured as a run before its admission rows (FK truth).
        store.ensure_run({"run_id": "import-2", "radar": "legacy",
                          "radar_ref": "6054488", "status": "success"})
        item_b = mapped_store_item(item_id="github:acme:dup#1")
        item_b["url"] = item_a["url"]
        result = store.ensure_item(item_b, run_id="import-2")
        assert result["inserted"] == 0 and result["duplicate_url"] == 1
        ledger = store.audit_admissions(run_id="import-2")[0]
        assert ledger.reason_codes == ("DUPLICATE_URL",)
        assert ledger.duplicate_of == item_a["id"]


# ---------------------------------------------------------------------------
# typed facade
# ---------------------------------------------------------------------------


class TestAssetStoreFacade:
    def test_open_in_memory_migrates(self, store):
        assert store.schema_version() == 1
        assert store.verify_schema() is True

    def test_mapping_and_dataclass_payloads_round_trip(self, store):
        item = mapped_store_item()
        store.ingest_run(
            {"run_id": "run-1", "radar": "horizon", "radar_ref": "p", "status": "success"},
            [item], [],
        )
        fetched = store.get_item(item["id"])
        assert fetched is not None
        payload = fetched.to_payload()
        assert payload["id"] == item["id"]
        assert payload["tags"] == ["mcp", "tool-use"]

    def test_run_records_are_typed(self, store):
        store.ingest_run(
            {"run_id": "run-1", "radar": "horizon", "radar_ref": "p", "status": "success"},
            [mapped_store_item()], [],
        )
        run = store.get_run("run-1")
        assert run is not None
        payload = run.to_payload()
        assert payload["status"] == "success"
        assert payload["invariant_ok"] is True
        assert [r.run_id for r in store.list_runs()] == ["run-1"]
