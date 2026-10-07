"""Fixture corpus, inventory, oracle, and determinism checks for the Horizon cutover baseline.

Ticket 04 (revised after verifier findings). All tests are read-only against production
``knowledge/``: they only read the sanitized copies under ``tests/fixtures/legacy_articles/``
and the production directory for provenance/count cross-checks (never write, move, or
delete anything).

Design notes:
- Fixture articles are *sanitized structural copies*: they preserve every schema
  characteristic (5 record shapes, colon/colon-free IDs, enum coverage, null author)
  but are NOT guaranteed byte-identical to production. Provenance is proven by the
  ``source_file`` + ``source_id`` + ``source_sha256`` recorded in ``inventory.json``.
- ``raw/`` and ``skipped_records.jsonl`` are fully sanitized minimal representatives
  (no production user text, no real usernames).
- Search/mapping behavior is compared against the static oracle files
  (``expected_mapped.jsonl``, ``expected_search.json``), not re-derived expectations.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.non_llm

FIXTURE_ROOT = Path(__file__).resolve().parent / "fixtures" / "legacy_articles"
PROJECT_ROOT = Path(__file__).resolve().parent.parent
REPO_ARTICLES_DIR = PROJECT_ROOT / "knowledge" / "articles"

CANONICAL_ID_OK = r"^[a-z0-9][a-z0-9:._-]*$"


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------
def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_inventory() -> dict:
    return json.loads((FIXTURE_ROOT / "inventory.json").read_text(encoding="utf-8"))


def _fixture_articles() -> list[tuple[Path, dict]]:
    articles = []
    for path in sorted((FIXTURE_ROOT / "articles").glob("*.json")):
        articles.append((path, json.loads(path.read_text(encoding="utf-8"))))
    return articles


def _skipped_rows() -> list[dict]:
    rows = []
    for line in (FIXTURE_ROOT / "skipped_records.jsonl").read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def _article_ids() -> set[str]:
    return {data["id"] for _, data in _fixture_articles()}


def _load_mapped_oracle() -> list[dict]:
    rows = []
    for line in (FIXTURE_ROOT / "expected_mapped.jsonl").read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def _load_search_oracle() -> dict:
    return json.loads((FIXTURE_ROOT / "expected_search.json").read_text(encoding="utf-8"))


# --------------------------------------------------------------------------
# 1. immutability: inventory counts, checksums, provenance
# --------------------------------------------------------------------------
class TestInventory:
    def test_row_counts_match_inventory(self):
        inv = _load_inventory()
        assert inv["row_counts"] == {"articles": 20, "skipped_records": 5, "raw_snapshots": 1}

    def test_every_file_checksum_matches(self):
        inv = _load_inventory()
        on_disk = {
            str(p.relative_to(FIXTURE_ROOT)): (_sha256(p), p.stat().st_size)
            for p in FIXTURE_ROOT.rglob("*")
            if p.is_file()
            and "__pycache__" not in p.parts
            and p.name != "inventory.json"
        }
        recorded = {e["path"]: (e["sha256"], e["bytes"]) for e in inv["files"]}
        assert set(recorded) == set(on_disk)
        for rel, (sha, size) in recorded.items():
            assert on_disk[rel] == (sha, size), f"fixture drift: {rel}"

    def test_article_provenance_recorded_and_verifiable(self):
        """Each article fixture records its production source file, id, and checksum."""
        inv = _load_inventory()
        entries = [e for e in inv["files"] if e["path"].startswith("articles/")]
        assert len(entries) == 20
        if not REPO_ARTICLES_DIR.exists():
            pytest.skip("production knowledge/ not present in this checkout")
        for entry in entries:
            assert entry["source_file"].startswith("knowledge/articles/")
            assert entry["source_sha256"], entry["path"]
            prod = PROJECT_ROOT / entry["source_file"]
            fixture = FIXTURE_ROOT / entry["path"]
            # provenance: the recorded source hash matches the live original
            assert _sha256(prod) == entry["source_sha256"], entry["path"]
            # structural lineage: sanitized fixture keeps the source record's identity
            # and URL even when body content is sanitized
            src = json.loads(prod.read_text(encoding="utf-8"))
            fix = json.loads(fixture.read_text(encoding="utf-8"))
            assert fix["id"] == src["id"] == entry["source_id"]
            assert fix["source_url"] == src["source_url"]

    def test_fixture_set_has_no_duplicate_urls(self):
        urls = [data["url"] for _, data in _fixture_articles()]
        assert len(urls) == len(set(urls)) == 20

    def test_production_baseline_counts_recorded(self):
        inv = _load_inventory()
        assert inv["production_baseline"] == {
            "commit": "6054488",
            "article_files_including_index": 625,
            "article_records_excluding_index": 624,
            "colon_id_records": 406,
            "skipped_rows": 77,
            "raw_snapshots": 4,
        }


# --------------------------------------------------------------------------
# 2. coverage invariants
# --------------------------------------------------------------------------
class TestCorpusCoverage:
    def test_exactly_twenty_articles(self):
        assert len(_fixture_articles()) == 20

    def test_colon_id_representation(self):
        ids = _article_ids()
        colon = {i for i in ids if ":" in i}
        plain = ids - colon
        assert len(colon) == 11
        assert len(plain) == 9
        assert "rss:mitchell-hashimoto-20260530-010" in colon  # discovery G1 example

    def test_all_source_type_enum_values_covered(self):
        seen = {data.get("source_type") for _, data in _fixture_articles()}
        assert seen == {
            "repository", "blog", "paper", "tutorial", "benchmark",
            "news", "discussion", "documentation", None,
        }

    def test_reading_priority_values_covered(self):
        seen = {data.get("reading_priority") for _, data in _fixture_articles()}
        assert {"study-now", "save-for-context", "low-priority", None} <= seen

    def test_null_author_records_present(self):
        nulls = [i for i, d in _fixture_articles() if d.get("author") is None]
        assert len(nulls) == 7

    def test_status_values(self):
        statuses = [d["status"] for _, d in _fixture_articles()]
        assert statuses.count("published") == 16
        assert statuses.count("review") == 4

    def test_legacy_description_carriers_present(self):
        carriers = [i for i, d in _fixture_articles() if "description" in d]
        assert len(carriers) == 3  # the MCP G7 dead-field scenario

    def test_id_equals_filename_stem(self):
        for path, data in _fixture_articles():
            assert path.stem == data["id"]

    def test_distinct_legacy_schemas_covered(self):
        """4 article record shapes (16/17/29/31 keys); index.json's list shape is
        covered by the production cross-check, not duplicated as a fixture."""
        keysets = {tuple(sorted(d.keys())) for _, d in _fixture_articles()}
        assert len(keysets) == 4
        sizes = {len(ks) for ks in keysets}
        assert sizes == {16, 17, 29, 31}

    def test_skipped_set_is_smallest_full_variant_cover(self):
        rows = _skipped_rows()
        assert len(rows) == 5
        stages = {r["stage"] for r in rows}
        assert stages == {"analyzer", "organizer"}
        reasons = [r["reason"] for r in rows]
        # analyzer variants: current 0.4 threshold + early 0.5 threshold
        assert any("threshold 0.4" in r for r in reasons)
        assert any("threshold 0.5" in r for r in reasons)
        # organizer variant: schema validation failure
        assert sum("schema validation failed" in r for r in reasons) == 2
        # distinct reason values cover every family without duplicate rows
        assert len(set(reasons)) == len(reasons) - 1  # key_insight appears twice (two ID regimes)

    def test_skipped_log_g2_audit_break_present(self):
        """Skipped IDs must include regimes that match no published fixture id."""
        published = _article_ids()
        skipped_ids = {r["id"] for r in _skipped_rows()}
        orphans = skipped_ids - published
        assert orphans, "G2 audit break not represented in fixture"
        # and at least one skipped row carries the analyzer's "unknown" attribution
        assert "unknown" in skipped_ids

    def test_raw_snapshot_sanitized_minimal(self):
        paths = sorted((FIXTURE_ROOT / "raw").glob("*.json"))
        assert len(paths) == 1
        data = json.loads(paths[0].read_text(encoding="utf-8"))
        assert isinstance(data, list) and 1 <= len(data) <= 5
        record = data[0]
        # collector-stage record schema (G2's collect-time ID namespace)
        for key in ("id", "title", "source", "source_url", "raw_description", "collected_at"):
            assert key in record
        # covers the null-author collector variant too
        assert any(r.get("author") is None for r in data)
        # sanitized: no real Reddit/github user content
        blob = json.dumps(data).lower()
        assert "reddit.com" not in blob
        assert not re.search(r"u/[a-z0-9_]{3,}", blob)

    def test_no_fixture_carries_reddit_user_content(self):
        """Sanitization guard across every fixture file."""
        forbidden = ("reddit.com/user/", "u/", "i.redd.it")
        for path in FIXTURE_ROOT.rglob("*"):
            if path.is_file() and path.suffix in {".json", ".jsonl"}:
                blob = path.read_text(encoding="utf-8").lower()
                for token in forbidden:
                    assert token not in blob, (path.name, token)

    SANITIZED_FIELDS = (
        "title", "author", "summary", "description",
        "raw_description", "key_insight", "relevance_reason",
    )

    def test_article_content_is_sanitized_against_production_source(self):
        """Regression: every non-null human-authored field differs from production;
        identity, URLs, key sets, null shape, and enum/score coverage are unchanged."""
        if not REPO_ARTICLES_DIR.exists():
            pytest.skip("production knowledge/ not present in this checkout")
        for path, fixture in _fixture_articles():
            source = json.loads((REPO_ARTICLES_DIR / path.name).read_text(encoding="utf-8"))
            # identity and lineage preserved
            assert fixture["id"] == source["id"]
            assert fixture["source_url"] == source["source_url"]
            assert fixture["url"] == source["url"]
            # exact key-set and null-shape preservation
            assert set(fixture.keys()) == set(source.keys())
            for field in self.SANITIZED_FIELDS:
                if field not in source:
                    continue
                assert (fixture.get(field) is None) == (source[field] is None), (path.name, field)
                if source[field] is not None:
                    assert fixture[field] != source[field], (path.name, field)
            # non-null authors must be the deterministic synthetic value, never real
            if fixture.get("author") is not None:
                assert fixture["author"] == f"fixture-author-{fixture['id']}"
                assert fixture["author"] != source["author"]
            # enum/status/score coverage preserved
            for field in (
                "status", "score", "relevance_score", "category", "source_type",
                "reading_priority", "audience", "suggested_action", "learning_track",
                "priority_score", "confidence", "learning_tags", "tags",
                "published_at", "collected_at", "updated_at",
            ):
                if field in source:
                    assert fixture[field] == source[field], (path.name, field)

    def test_sanitized_content_is_deterministic(self):
        """Regenerating must yield identical text (no timestamp randomness)."""
        for path, fixture in _fixture_articles():
            if fixture.get("summary"):
                assert fixture["summary"].startswith(
                    f"Sanitized summary fixture content for legacy record {fixture['id']}."
                )
            if fixture.get("title"):
                assert fixture["title"] == (
                    f"Sanitized title fixture content for legacy record {fixture['id']}."
                )


# --------------------------------------------------------------------------
# 4. production corpus cross-check (read-only)
# --------------------------------------------------------------------------
class TestProductionCrossCheck:
    def test_production_corpus_untouched_baseline_counts(self):
        """The live corpus must still hold the baseline in inventory.json (read-only)."""
        if not REPO_ARTICLES_DIR.exists():
            pytest.skip("production knowledge/ not present in this checkout")
        article_files = [
            p for p in REPO_ARTICLES_DIR.glob("*.json") if p.name != "index.json"
        ]
        assert len(article_files) == 624  # 625 *.json including index.json
        colon = [p for p in article_files if ":" in p.stem]
        assert len(colon) == 406


# --------------------------------------------------------------------------
# 5. static oracle: mapping + search expectations (no self-derivation)
# --------------------------------------------------------------------------
class TestStaticOracleMapping:
    @pytest.fixture(autouse=True)
    def _fixture_path(self):
        sys.path.insert(0, str(FIXTURE_ROOT))
        yield
        sys.path.remove(str(FIXTURE_ROOT))

    def test_oracle_covers_every_fixture_article_exactly(self):
        oracle = _load_mapped_oracle()
        assert len(oracle) == 20
        assert {r["fixture_file"] for r in oracle} == {
            p.name for p, _ in _fixture_articles()
        }

    def test_implementation_mapping_matches_static_oracle(self):
        from expected_mapping import map_legacy_article

        oracle = {r["fixture_file"]: r for r in _load_mapped_oracle()}
        for path, data in _fixture_articles():
            row = map_legacy_article(data)
            expected = oracle[path.name]
            assert row == {k: v for k, v in expected.items() if k != "fixture_file"}, path.name

    def test_oracle_encodes_ticket02_identity_rule(self):
        """Every mapped id must be minted as legacy:<legacy id>, colon-legal."""
        for row in _load_mapped_oracle():
            assert row["id"] == "legacy:" + row["legacy_id"]
            assert row["id"].startswith("legacy:")
            assert re.match(CANONICAL_ID_OK, row["id"])
            assert row["legacy_id_has_colon"] == (":" in row["legacy_id"])

    def test_oracle_null_propagation_and_drops(self):
        null_author = [r for r in _load_mapped_oracle() if r["author"] is None]
        assert len(null_author) == 7
        null_type = [r for r in _load_mapped_oracle() if r["source_type"] is None]
        assert len(null_type) == 10
        for row in _load_mapped_oracle():
            for dropped in ("personal_fit_score", "reading_priority", "learning_tags"):
                assert dropped not in row

    def test_oracle_content_main_only_from_description_carriers(self):
        oracle = _load_mapped_oracle()
        carriers = [r for r in oracle if r["content_main"] is not None]
        assert len(carriers) == 3


class TestStaticOracleSearch:
    @pytest.fixture(autouse=True)
    def _fixture_path(self):
        sys.path.insert(0, str(FIXTURE_ROOT))
        yield
        sys.path.remove(str(FIXTURE_ROOT))

    def test_implementation_search_matches_static_oracle(self):
        from expected_mapping import implementation_search_hits

        corpus = [data for _, data in _fixture_articles()]
        oracle = _load_search_oracle()
        for keyword, expected in oracle["queries"].items():
            assert implementation_search_hits(keyword, corpus, limit=20) == expected, keyword

    def test_oracle_sanity_floor(self):
        oracle = _load_search_oracle()
        assert oracle["sanity_floor"]["must_return_nonempty"] == ["sanitized"]
        top = oracle["sanity_floor"]["top_hit"]
        assert top["expected_top"] == "legacy:rss:reddit-r-machinelearning-20260519-013"
        assert top["expected_top"] in oracle["queries"][top["query"]]

    def test_oracle_no_hit_for_unrelated_tokens(self):
        assert _load_search_oracle()["queries"]["zzz-no-match-token"] == []


# --------------------------------------------------------------------------
# 6. backup/restore procedure guard: the documented commands exist
# --------------------------------------------------------------------------
class TestProcedureDoc:
    def test_backup_doc_lists_required_steps(self):
        doc = (FIXTURE_ROOT / "BACKUP_RESTORE.md").read_text(encoding="utf-8")
        for token in ("SHA256SUMS", "MANIFEST", "jsonl", "Restore", "row-count", "cd \"$BACKUP\""):
            assert token in doc, token
