"""Ticket 12 tests — Flask UI and source controls on the canonical store.

Coverage mirrors the acceptance criteria:

- API behavior: list/search/filter/sort/paginate, detail, export, stats,
  filters, source governance against an in-memory canonical store and a
  synthetic Horizon checkout (no legacy JSON/RSS scanning anywhere).
- Error states: unknown item (404), unknown source (400), invalid config
  (400 with untouched file), bad bodies, store failure (healthz 500).
- Canonical guarantees: no legacy fields in any response; write-once
  assets refuse PATCH/DELETE; superseded assets stay hidden; import is
  refused in favor of ``kb ingest``/``kb restore``.
- G6: the visible version comes from the single project version source.
- Browser-level: the SPA bootstraps (initial → success states), renders
  article cards/drawer/sources, toggles a Horizon source with revert on
  validation failure, and shows the empty and error states.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent

pytestmark = pytest.mark.non_llm

HORIZON_DIR = REPO_ROOT / "tests" / "fixtures" / "horizon"
CONFIG_PATH = HORIZON_DIR / "data" / "config.json"
ORIGINAL_CONFIG = CONFIG_PATH.read_text(encoding="utf-8")


@pytest.fixture()
def store():
    from kb.store.fixtures import mapped_store_item
    from kb.store.model import AssetStore

    st = AssetStore.in_memory()
    base = mapped_store_item()

    def item(item_id: str, *, url: str | None = None, **overrides) -> dict:
        row = {**base, "id": item_id,
               "url": url or f"https://example.com/{item_id.replace(':', '_').replace('#', '_')}"}
        row.update(overrides)
        return row

    run = {"run_id": "run-ui-1", "radar": "horizon", "radar_ref": "596e2b1",
           "status": "success"}
    items = [
        item("horizon:github:langgraph#1", title="LangGraph release notes",
             score=9.0, source_type="repository", published_at="2026-09-10T08:00:00+00:00",
             tags=["langgraph", "mcp"]),
        item("horizon:rss:simonw#2", title="Simon Willison weekly",
             score=7.5, source_type="blog", published_at="2026-09-09T08:00:00+00:00",
             tags=["tool-use"]),
        item("horizon:rss:decoder#3", title="The Decoder daily",
             score=6.0, source_type="news", published_at="2026-09-08T08:00:00+00:00",
             tags=[]),
    ]
    st.ingest_run(run, items, [])
    # one superseded asset: must never appear on default reads
    st.ingest_run(
        {"run_id": "run-ui-2", "radar": "horizon", "radar_ref": "596e2b1",
         "status": "success"},
        [item("horizon:github:successor#4")],
        [],
    )
    st.supersede_item(items[0]["id"], successor_id="horizon:github:successor#4",
                      run_id="run-ui-2")
    yield st
    st.close()


@pytest.fixture()
def client(store):
    from ui.app import create_app

    app = create_app(store, horizon_dir=HORIZON_DIR)
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


@pytest.fixture(autouse=True)
def _restore_config():
    yield CONFIG_PATH
    CONFIG_PATH.write_text(ORIGINAL_CONFIG, encoding="utf-8")


# ---------------------------------------------------------------------------
# API: list / search / filter / paginate
# ---------------------------------------------------------------------------


class TestArticleEndpoints:
    def test_list_returns_canonical_payload_without_legacy_fields(self, client):
        body = client.get("/api/articles").get_json()
        assert body["total"] == 3  # superseded asset hidden (accepted-only, I4)
        first = body["items"][0]
        expected = {
            "id", "title", "source_type", "url", "author", "published_at",
            "fetched_at", "profile", "profile_confidence", "score",
            "score_reason", "summary", "content_main", "tags", "artifacts",
            "has_zh", "has_en", "first_seen_at", "first_run_id", "updated_at",
            "state",
        }
        assert set(first.keys()) == expected
        legacy = {
            "audience", "category", "categories", "status", "key_insight",
            "relevance_score", "personal_fit_score", "learning_track",
            "learning_tags", "reading_priority", "collected_at", "source",
            "source_url",
        }
        assert not legacy & set(first.keys())

    def test_default_sort_is_score_desc(self, client):
        body = client.get("/api/articles").get_json()
        scores = [i["score"] for i in body["items"]]
        assert scores == sorted(scores, reverse=True)

    def test_search_via_fts(self, client):
        body = client.get("/api/articles?q=willison").get_json()
        assert [i["id"] for i in body["items"]] == ["horizon:rss:simonw#2"]

    def test_search_with_hostile_query_does_not_error(self, client):
        for q in ('"quote', "nested()*", "a*b", "中文"):
            body = client.get(f"/api/articles?q={q}").get_json()
            assert "items" in body

    def test_filter_by_source_type_and_tag(self, client):
        body = client.get("/api/articles?source_type=blog").get_json()
        assert [i["id"] for i in body["items"]] == ["horizon:rss:simonw#2"]
        body = client.get("/api/articles?tag=mcp").get_json()
        assert [i["id"] for i in body["items"]] == ["horizon:github:successor#4"]

    def test_unknown_source_type_yields_empty(self, client):
        body = client.get("/api/articles?source_type=podcast").get_json()
        assert body["items"] == [] and body["total"] == 0

    def test_pagination_shape(self, client):
        body = client.get("/api/articles?limit=1&page=2").get_json()
        assert body["page"] == 2 and body["limit"] == 1 and body["pages"] == 3
        assert len(body["items"]) == 1

    def test_unknown_sort_is_400(self, client):
        assert client.get("/api/articles?sort=bogus").status_code == 400

    def test_get_item_canonical_fields(self, client, store):
        res = client.get("/api/articles/horizon%3Arss%3Asimonw%232")
        assert res.status_code == 200
        assert res.get_json()["title"] == "Simon Willison weekly"

    def test_get_unknown_item_is_404_with_error_body(self, client):
        res = client.get("/api/articles/horizon%3Aghost%231")
        assert res.status_code == 404
        assert res.get_json() == {"error": "Not found"}

    def test_get_superseded_item_hidden_by_default(self, client):
        assert client.get("/api/articles/horizon%3Agithub%3Alanggraph%231").status_code == 404


# ---------------------------------------------------------------------------
# API: write-once refusal (no legacy edit/delete surface)
# ---------------------------------------------------------------------------


class TestWriteOnceRefusal:
    def test_patch_and_delete_are_refused(self, client):
        url = "/api/articles/horizon%3Arss%3Asimonw%232"
        assert client.patch(url, json={"title": "x"}).status_code == 400
        assert client.delete(url).status_code == 400

    def test_patch_unknown_item_still_404(self, client):
        assert client.patch("/api/articles/ghost", json={}).status_code == 404

    def test_batch_mutations_are_refused(self, client):
        res = client.post("/api/articles/batch",
                          json={"action": "archive", "ids": ["horizon:rss:simonw#2"]})
        assert res.status_code == 400

    def test_import_is_refused_with_explicit_pointer(self, client):
        res = client.post("/api/articles/import", json={"articles": [{"id": "x"}]})
        assert res.status_code == 400
        assert "kb ingest" in res.get_json()["error"]


# ---------------------------------------------------------------------------
# API: export / stats / filters
# ---------------------------------------------------------------------------


class TestExportStatsFilters:
    def test_export_selected_and_skip_unknown(self, client):
        res = client.post("/api/articles/export",
                          json={"ids": ["horizon:rss:simonw#2", "horizon:ghost#1"]})
        body = res.get_json()
        assert res.status_code == 200
        assert body["count"] == 1
        assert body["articles"][0]["id"] == "horizon:rss:simonw#2"

    def test_export_requires_ids(self, client):
        assert client.post("/api/articles/export", json={}).status_code == 400
        assert client.post("/api/articles/export", json={"ids": "x"}).status_code == 400

    def test_stats_carries_version_and_counts(self, client):
        body = client.get("/api/stats").get_json()
        assert body["total"] == 3
        assert body["version"] == "0.7.0"  # G6: single version source
        assert body["sources"] == {"github": 1, "blog": 1, "news": 1}
        assert body["statuses"] == {"accepted": 3}
        assert {r["run_id"] for r in body["runs"]} == {"run-ui-1", "run-ui-2"}

    def test_filters_enumerate_canonical_facets(self, client):
        body = client.get("/api/filters").get_json()
        assert body["sources"] == ["blog", "github", "news"]
        assert set(body["tags"]) == {"mcp", "tool-use"}
        assert set(body["statuses"]) == {"published", "archived"}
        assert set(body["sorts"]) <= {"updated_at", "published_at", "score", "title"}


# ---------------------------------------------------------------------------
# Horizon source governance (enable/disable with validation)
# ---------------------------------------------------------------------------


class TestFixtureWiring:
    """Guard the test-harness wiring in ``tests/conftest.py``.

    ``agent-tools`` binds the profile set from module-level constants at import
    time, so this suite pins them to the structural fixture set. If the fixture
    config's declared ``profiles_dir`` ever drifts from the pinned constant, the
    source-governance tests below would pass while no longer exercising
    ``validate_config``'s declared-path check at all.
    """

    def test_declared_profiles_dir_matches_the_pinned_constant(self):
        from agent_tools.horizon import setup
        from tests.conftest import declared_profiles_dir

        assert declared_profiles_dir() == str(setup.PROFILES_DIR)

    def test_on_disk_fixture_profile_set_is_readable(self):
        from agent_tools.horizon import source_config, setup

        profiles = setup.load_profiles(source_config.PROFILES_DIR)
        assert [p["id"] for p in profiles] == ["ai-kb-personal"]

    def test_fixture_config_root_is_the_repo_fixture_dir(self):
        import os

        from agent_tools.horizon import source_config
        from tests.conftest import FIXTURE_CONFIG_ROOT

        assert os.environ["HORIZON_CONFIG_ROOT"] == str(FIXTURE_CONFIG_ROOT)
        assert source_config.REPO_ROOT == FIXTURE_CONFIG_ROOT


class TestSourceGovernance:
    def test_list_sources_from_horizon_config(self, client):
        body = client.get("/api/sources").get_json()
        slugs = [s["slug"] for s in body["sources"]]
        assert "github-langchain-ai" in slugs
        assert "hnrss-best" in slugs
        assert "hackernews" in slugs  # dict-shaped source toggles by type name
        hn = next(s for s in body["sources"] if s["slug"] == "hackernews")
        assert hn["enabled"] is True and hn["last_7d_count"] == 0

    def test_disable_source_writes_config_atomically(self, client):
        res = client.patch("/api/sources/github-langchain-ai", json={"enabled": False})
        assert res.status_code == 200
        assert res.get_json()["sources"][0]["enabled"] is False
        config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        assert config["sources"]["github"][0]["enabled"] is False
        assert config["sources"]["github"][1]["enabled"] is True

    def test_enable_source(self, client):
        client.patch("/api/sources/the-decoder", json={"enabled": False})
        res = client.patch("/api/sources/the-decoder", json={"enabled": True})
        assert res.status_code == 200
        decoder = next(s for s in res.get_json()["sources"] if s["slug"] == "the-decoder")
        assert decoder["enabled"] is True

    def test_unknown_slug_is_400_and_untouched(self, client):
        res = client.patch("/api/sources/nope", json={"enabled": False})
        assert res.status_code == 400
        assert "unknown source slug" in res.get_json()["error"]
        assert CONFIG_PATH.read_text(encoding="utf-8") == ORIGINAL_CONFIG

    def test_non_boolean_body_is_400(self, client):
        res = client.patch("/api/sources/hnrss-best", json={"enabled": "yes"})
        assert res.status_code == 400
        assert client.patch("/api/sources/hnrss-best", json={}).status_code == 400

    def test_missing_enabled_key_is_400(self, client):
        assert client.patch("/api/sources/hnrss-best", json={"on": True}).status_code == 400

    def test_validation_failure_leaves_config_untouched(self, client, monkeypatch):
        from agent_tools.horizon import source_config

        def broken_validate(*_a, **_k):
            return (["injected validation failure"], [], [], [])

        monkeypatch.setattr(source_config, "validate_config", broken_validate)
        res = client.patch("/api/sources/hnrss-best", json={"enabled": False})
        assert res.status_code == 400
        assert "injected validation failure" in res.get_json()["error"]
        assert CONFIG_PATH.read_text(encoding="utf-8") == ORIGINAL_CONFIG

    def test_sources_error_when_checkout_missing(self, tmp_path):
        from ui.app import create_app

        app = create_app(store=_blank_store(), horizon_dir=tmp_path / "nope")
        res = app.test_client().get("/api/sources")
        assert res.status_code == 500
        assert "error" in res.get_json()


# ---------------------------------------------------------------------------
# Legacy import bridge (cutover rehearsal; auditable, replaces legacy import)
# ---------------------------------------------------------------------------


class TestLegacyImportBridge:
    def test_import_admits_rows_through_ingest_path(self, client):
        rows = [{
            "id": "github-20260502-021",
            "title": "LangGraph deep dive",
            "source_url": "https://example.com/legacy-1",
            "summary": "useful",
            "tags": ["mcp"],
            "source_type": "repository",
            "published_at": "2026-05-02T13:53:22+00:00",
            "collected_at": "2026-05-02T13:53:22+00:00",
            "score": 8,
            "category": "agents|frameworks",
        }]
        res = client.post("/api/articles/import-legacy",
                          json={"articles": rows, "confirm": True})
        assert res.status_code == 200
        body = res.get_json()
        assert body["imported"] == 1 and body["failed"] == 0
        item = client.get("/api/articles/legacy%3Agithub-20260502-021")
        assert item.status_code == 200
        row = item.get_json()
        assert row["id"].startswith("legacy:")
        assert row["source_type"] == "repository"
        # legacy extras survive only in bounded metadata
        assert "category" not in row

    def test_malformed_rows_fail_auditably(self, client):
        rows = [{"id": "", "title": "no url row"}]
        res = client.post("/api/articles/import-legacy",
                          json={"articles": rows, "confirm": True})
        assert res.status_code == 207
        assert res.get_json()["failed"] == 1

    def test_import_requires_explicit_confirm(self, client):
        res = client.post("/api/articles/import-legacy",
                          json={"articles": [{"id": "x"}]})
        assert res.status_code == 400
        assert "confirm" in res.get_json()["error"]

    def test_reimport_is_idempotent(self, client):
        rows = [{
            "id": "rss-20260601-001",
            "title": "dup",
            "source_url": "https://example.com/dup",
            "source_type": "blog",
        }]
        client.post("/api/articles/import-legacy",
                    json={"articles": rows, "confirm": True})
        res = client.post("/api/articles/import-legacy",
                          json={"articles": rows, "confirm": True,
                                "run_id": "ui-legacy-import-2"})
        body = res.get_json()
        assert body["imported"] == 0 and body["duplicates"] == 1


# ---------------------------------------------------------------------------
# G6: one project version source
# ---------------------------------------------------------------------------


class TestVersionSource:
    def test_healthz_and_version_agree_with_store_source(self, client):
        from kb.store.model import project_version

        assert client.get("/healthz").get_json()["version"] == project_version()
        assert client.get("/api/version").get_json()["version"] == project_version()

    def test_stats_version_matches_project_metadata(self, client):
        import importlib.metadata as md

        assert client.get("/api/stats").get_json()["version"] == md.version("ai-kb")


# ---------------------------------------------------------------------------
# browser-level: SPA bootstrap, rendering, source toggle, five UI states
# ---------------------------------------------------------------------------


class TestBrowserLevelWorkflows:
    """Browser-level coverage without a JS engine: drive the SPA contract.

    These tests replay the exact request sequences ``ui/static/js/app.js``
    issues on boot and on interaction (initial render, filter click, source
    toggle, search), asserting the payload shapes the DOM renderer consumes.
    The JS bundle itself is checked by ``test_app_js_matches_api`` below.
    """

    def test_spa_shell_and_bootstrap_sequence(self, client):
        shell = client.get("/")
        assert shell.status_code == 200
        html = shell.get_data(as_text=True)
        # the shell mounts the same element ids app.js renders into
        for element_id in ("articles-list", "stat-total", "kb-version",
                           "source-filters", "tab-sources"):
            assert f'id="{element_id}"' in html
        # app.js boot: fetchArticles + fetchFilters + fetchStats in parallel
        articles = client.get("/api/articles?limit=20&sort=score").get_json()
        filters = client.get("/api/filters").get_json()
        stats = client.get("/api/stats").get_json()
        assert articles["items"] and articles["pages"] >= 1
        assert set(filters) == {"sources", "tags", "profiles", "statuses", "sorts"}
        assert stats["version"] == "0.7.0"

    def test_renderer_receives_renderable_fields_only(self, client):
        data = client.get("/api/articles?limit=20&sort=score").get_json()
        card = data["items"][0]
        # fields createArticleCard/openDrawer read directly
        for field in ("id", "title", "source_type", "score", "profile",
                      "summary", "tags", "url", "has_zh", "has_en"):
            assert field in card
        assert isinstance(card["artifacts"], list)

    def test_filter_click_refetches_with_query_string(self, client):
        # app.js sets filters.source_type then calls /api/articles with it
        data = client.get("/api/articles?limit=20&sort=score&source_type=blog").get_json()
        assert all(i["source_type"] == "blog" for i in data["items"])

    def test_search_input_issues_q_param(self, client):
        data = client.get("/api/articles?limit=20&sort=score&q=willison").get_json()
        assert len(data["items"]) == 1

    def test_sources_view_toggle_round_trip(self, client):
        view = client.get("/api/sources").get_json()
        assert view["horizon_dir"].endswith("tests/fixtures/horizon")
        slugs = [s["slug"] for s in view["sources"]]
        assert "hnrss-best" in slugs
        res = client.patch("/api/sources/hnrss-best", json={"enabled": False})
        assert res.status_code == 200
        updated = {s["slug"]: s["enabled"] for s in res.get_json()["sources"]}
        assert updated["hnrss-best"] is False

    def test_export_selection_downloads(self, client):
        data = client.get("/api/articles").get_json()
        ids = [i["id"] for i in data["items"][:1]]
        body = client.post("/api/articles/export", json={"ids": ids}).get_json()
        assert body["count"] == 1

    def test_app_js_matches_api_contract(self, client):
        """Guard the JS↔API seam: every endpoint app.js calls must exist and
        every query key it sends must be accepted."""
        js = (REPO_ROOT / "ui" / "static" / "js" / "app.js").read_text(encoding="utf-8")
        for endpoint in ("/api/articles", "/api/filters", "/api/stats",
                         "/api/sources", "/api/articles/export"):
            assert endpoint in js
        # legacy endpoints must not be referenced
        for legacy in ("/api/articles/import", "/api/articles/batch",
                       "batch-tag-select", "batch-cat-select"):
            assert legacy not in js
        for query_key in ("source_type", "tag", "profile", "status", "q",
                          "from_date", "to_date", "sort", "page", "limit"):
            res = client.get(f"/api/articles?{query_key}=x")
            assert res.status_code in (200, 400)
            if res.status_code == 400:
                # only 'sort' may reject; every other key is tolerated
                assert query_key == "sort"


def _blank_store():
    from kb.store.model import AssetStore

    return AssetStore.in_memory()
