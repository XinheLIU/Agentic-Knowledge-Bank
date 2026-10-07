"""Contract tests: MCP knowledge server over the canonical SQLite store (ticket 11).

Closes discovery G7 (stale MCP fields). Tests build a minimal isolated store
per test with ``AssetStore.open`` + one ``ingest_run`` item and invoke the
module's public functions directly; the stdio JSON-RPC framing is exercised
through ``main()`` with patched stdin/stdout.

Guards:
- Launch compatibility: initialize / notifications/initialized / tools/list /
  tools/call keep working over stdio framing.
- Canonical fields only: no legacy ``relevance_score``/``stars``/``forks``/
  ``score_breakdown``/``analyzed_at``/``N/A`` anywhere in responses.
- Reader API only: no direct SQL or legacy JSON scanning in the server module.
- Explicit behavior: missing store, empty store, not-found, Unicode,
  malformed requests.
"""

from __future__ import annotations

import inspect
import json
import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from kb.store.fixtures import mapped_store_item
from kb.store.model import AssetStore

pytestmark = pytest.mark.non_llm

PROJECT_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture()
def server_module(tmp_path, monkeypatch):
    """Import the server against a per-test store path env override."""
    monkeypatch.setenv("KB_STORE_PATH", str(tmp_path / "kb.sqlite"))
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    sys.modules.pop("mcp_knowledge_server", None)
    import mcp_knowledge_server as mod

    yield mod
    sys.modules.pop("mcp_knowledge_server", None)


def _seed(store, item_id="horizon:acme:widget#1", **kwargs):
    """Ingest exactly one valid item through the store's ingest_run seam."""
    store.ingest_run(
        {"run_id": "r1", "radar": "horizon", "radar_ref": "test",
         "status": "success", "fetched": 1, "mapped": 1},
        [mapped_store_item(item_id=item_id, **kwargs)],
        [],
    )
    store._conn.commit()


@pytest.fixture()
def seeded_store(server_module):
    """A store file at KB_STORE_PATH already containing one accepted item."""
    mod = server_module
    store = AssetStore.open(mod.store_path())
    _seed(store)
    store.close()
    return mod


# ---------------------------------------------------------------------------
# 1. Store resolution: never scans knowledge/, never creates the store
# ---------------------------------------------------------------------------


class TestStoreResolution:
    def test_missing_store_is_not_created_and_tools_report_it(
        self, server_module, tmp_path
    ):
        missing = tmp_path / "absent" / "kb.sqlite"
        with patch.object(server_module, "store_path", return_value=missing):
            assert server_module.open_store(missing) is None
            assert not missing.exists()  # read-only consumer never creates it
            assert "not initialized" in server_module.knowledge_stats()
            assert "not initialized" in server_module.search_articles("anything")
            assert "not found" in server_module.get_article("horizon:ghost")

    def test_no_legacy_json_scanning_or_direct_sql_in_server_module(
        self, server_module
    ):
        source = inspect.getsource(server_module)
        for fragment in ("knowledge/articles", "ARTICLES_DIR", "load_articles",
                         "SELECT ", "INSERT ", "UPDATE ", "execute("):
            assert fragment not in source, fragment


# ---------------------------------------------------------------------------
# 2. Launch compatibility: stdio JSON-RPC framing
# ---------------------------------------------------------------------------


def _rpc(mod, method, params=None, rpc_id=None):
    msg = {"jsonrpc": "2.0", "method": method}
    if params is not None:
        msg["params"] = params
    if rpc_id is not None:
        msg["id"] = rpc_id
    with patch.object(sys, "stdin") as fake_stdin:
        fake_stdin.readline.side_effect = [json.dumps(msg) + "\n", ""]
        with patch.object(sys, "stdout") as fake_stdout:
            lines: list[str] = []
            fake_stdout.write.side_effect = lines.append
            fake_stdout.flush = lambda: None
            mod.main()
    assert lines, f"no response for {method}"
    return json.loads(lines[0])


class TestLaunchCompatibility:
    def test_stdio_handshake_and_tool_listing(self, server_module):
        init = _rpc(server_module, "initialize",
                    {"protocolVersion": "2024-11-05"}, rpc_id=1)
        assert init["id"] == 1
        assert init["result"]["serverInfo"]["name"] == "knowledge-mcp"
        assert init["result"]["protocolVersion"] == "2024-11-05"
        tools = _rpc(server_module, "tools/list", rpc_id=2)
        names = {t["name"] for t in tools["result"]["tools"]}
        assert names == {"search_articles", "get_article", "knowledge_stats"}

    def test_initialized_notification_is_silent(self, server_module):
        with patch.object(sys, "stdin") as fake_stdin:
            fake_stdin.readline.side_effect = [
                json.dumps({"jsonrpc": "2.0",
                            "method": "notifications/initialized"}) + "\n", ""]
            with patch.object(sys, "stdout") as fake_stdout:
                written: list[str] = []
                fake_stdout.write.side_effect = written.append
                fake_stdout.flush = lambda: None
                server_module.main()
        assert written == []

    def test_tools_call_via_stdio_returns_text_content(self, seeded_store):
        resp = _rpc(seeded_store, "tools/call",
                    {"name": "knowledge_stats", "arguments": {}}, rpc_id=7)
        text = resp["result"]["content"][0]["text"]
        assert "Total articles: 1" in text

    def test_real_subprocess_launch_compatibility(self, seeded_store, tmp_path):
        """The exact command client configs use launches and answers."""
        import shutil

        env_store = tmp_path / "launch" / "kb.sqlite"
        env_store.parent.mkdir(parents=True)
        shutil.copy(Path(seeded_store.store_path()), env_store)
        env = dict(os.environ)
        env["KB_STORE_PATH"] = str(env_store)
        env.pop("PYTEST_CURRENT_TEST", None)  # production read-only path
        proc = subprocess.run(
            [sys.executable, str(PROJECT_ROOT / "mcp_knowledge_server.py")],
            input="\n".join([
                json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize",
                            "params": {"protocolVersion": "2024-11-05"}}),
                json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}),
                json.dumps({"jsonrpc": "2.0", "id": 2, "method": "tools/list"}),
                json.dumps({"jsonrpc": "2.0", "id": 3, "method": "tools/call",
                            "params": {"name": "knowledge_stats",
                                       "arguments": {}}}),
            ]) + "\n",
            capture_output=True, text=True, timeout=60,
            cwd=PROJECT_ROOT, env=env,
        )
        assert proc.returncode == 0, proc.stderr
        replies = [json.loads(line) for line in proc.stdout.splitlines()
                   if line.strip()]
        assert [r.get("id") for r in replies] == [1, 2, 3]
        stats_text = replies[2]["result"]["content"][0]["text"]
        assert "Total articles: 1" in stats_text


# ---------------------------------------------------------------------------
# 3. Tool behavior against an isolated store (canonical fields only, G7)
# ---------------------------------------------------------------------------

LEGACY_FIELD_TOKENS = (
    "relevance_score", "stars", "forks", "score_breakdown",
    "analyzed_at", "N/A",
)


class TestToolBehavior:
    def test_empty_store_reports_zero_explicitly(self, server_module):
        store = AssetStore.open(server_module.store_path())
        store.close()
        text = server_module.knowledge_stats()
        assert "Total articles: 0" in text
        for token in LEGACY_FIELD_TOKENS:
            assert token not in text

    def test_search_finds_seeded_item_canonical_fields_only(self, seeded_store):
        text = seeded_store.search_articles("Horizon item")
        assert "■ A Horizon item" in text
        assert "(id: horizon:horizon:acme:widget#1" in text
        assert "Score: 8" in text
        for token in LEGACY_FIELD_TOKENS:
            assert token not in text

    def test_search_empty_result_is_explicit(self, seeded_store):
        assert seeded_store.search_articles("zzz-no-match-token") == (
            "No articles found for 'zzz-no-match-token'"
        )

    def test_search_source_type_filter_structured_and_cjk_unicode(
        self, server_module
    ):
        """CJK matching is lossless through the reader seam."""
        store = AssetStore.open(server_module.store_path())
        _seed(store, item_id="horizon:cjk:one#1",
              title="LangGraph 有状态工作流实战")
        store.close()
        text = server_module.search_articles("工作流")
        assert "LangGraph 有状态工作流实战" in text
        text = server_module.search_articles("Horizon item",
                                             source_type="paper")
        assert text == "No articles found for 'Horizon item'"

    def test_get_article_real_stored_data_explicit_nulls(self, seeded_store):
        text = seeded_store.get_article("horizon:horizon:acme:widget#1")
        assert "id: horizon:horizon:acme:widget#1" in text
        assert "state: accepted" in text
        assert "source_type: github" in text
        assert "url: https://example.com/" in text
        assert "author: null" in text  # explicit null, never N/A
        assert "summary: 有用的摘要 with mechanism" in text
        for token in LEGACY_FIELD_TOKENS:
            assert token not in text

    def test_get_article_not_found_is_explicit(self, seeded_store):
        assert seeded_store.get_article("horizon:does-not-exist") == (
            "Article 'horizon:does-not-exist' not found."
        )

    def test_stats_counts_match_store(self, seeded_store):
        store = AssetStore.open(seeded_store.store_path())
        stats = store.stats()
        store.close()
        text = seeded_store.knowledge_stats()
        assert f"Total articles: {stats.item_count}" in text
        assert f"  Accepted assets: {stats.accepted_count}" in text
        assert f"  Ingestion runs: {stats.run_count}" in text
        assert "Top tags:" in text and "mcp: 1" in text
        assert "Average score: 8.00" in text
        for token in LEGACY_FIELD_TOKENS:
            assert token not in text


# ---------------------------------------------------------------------------
# 4. Malformed requests (error behavior is explicit)
# ---------------------------------------------------------------------------


class TestMalformedRequests:
    def test_unknown_tool_is_invalid_request_error(self, server_module):
        resp = _rpc(server_module, "tools/call",
                    {"name": "no_such_tool", "arguments": {}}, rpc_id=9)
        assert resp["error"]["code"] == -32601

    def test_missing_required_argument_is_invalid_params(self, seeded_store):
        resp = _rpc(seeded_store, "tools/call",
                    {"name": "search_articles", "arguments": {}}, rpc_id=10)
        assert resp["error"]["code"] == -32602

    def test_unknown_method_error(self, server_module):
        resp = _rpc(server_module, "wat/method", rpc_id=12)
        assert resp["error"]["code"] == -32601
        assert resp["id"] == 12

    def test_malformed_json_line_skipped_server_keeps_serving(
        self, seeded_store, capsys
    ):
        mod = seeded_store
        good = json.dumps({"jsonrpc": "2.0", "id": 5, "method": "tools/list"})
        with patch.object(sys, "stdin") as fake_stdin:
            fake_stdin.readline.side_effect = ["{not json}\n", good + "\n", ""]
            mod.main()
        out = capsys.readouterr().out
        replies = [json.loads(line) for line in out.splitlines() if line.strip()]
        assert len(replies) == 1
        assert replies[0]["id"] == 5
        assert "tools" in replies[0]["result"]
