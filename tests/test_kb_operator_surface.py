"""KB operator-surface tests — asset identity, mapping, summaries, storage CLI.

Covers the parts of the operator surface that stay with the knowledge base: the
canonical asset-ID rule and prototype mapper in ``kb.horizon.contract``, the
one-line summary / exit-code vocabulary, and the ``serve`` / ``export`` /
``backup`` / ``restore`` storage commands. Collection-side run behavior is not
tested here — it is owned by Information Assistant and agent-tools.
"""

from __future__ import annotations

import json

import pytest

from kb import cli
from kb.horizon.contract import (
    ExitCode,
    map_item,
    mint_asset_id,
    selected_profile,
    summary,
)

pytestmark = pytest.mark.non_llm


def _item(item_id: str = "github:repo:xyz", source_type: str = "github", **extra) -> dict:
    base = {
        "id": item_id,
        "source_type": source_type,
        "title": "A Horizon item",
        "url": f"https://example.com/{item_id}",
        "author": None,
        "published_at": "2026-09-11T08:00:00+00:00",
        "fetched_at": "2026-09-11T09:00:00+00:00",
        "profile": ["tech-news", "agent-systems"],
        "processing": {
            "classification": {
                "profile": "tech-news",
                "method": "ai_match",
                "confidence": 0.9,
                "reason": "matches P0 topics",
            },
            "analysis": {
                "score": 8,
                "reason": "directly relevant",
                "summary": "有用的摘要",
                "tags": ["mcp", "tool-use", "mcp"],
            },
            "artifacts": {
                "zh": {
                    "title": "中文标题",
                    "blocks": [
                        {"id": "b1", "title": "块一", "content": "正文", "primary": True,
                         "source_refs": ["s1"]},
                        {"id": "b2", "title": None, "content": "尾注", "primary": False,
                         "source_refs": []},
                    ],
                    "sources": [{"id": "s1", "title": "源", "url": "https://example.com/s1"}],
                }
            },
        },
        "metadata": {"stars": 12},
    }
    base.update(extra)
    return base


# ---------------------------------------------------------------------------
# KB-owned identity and mapping policies
# ---------------------------------------------------------------------------


class TestContractPolicies:
    def test_selected_profile_from_classification_not_route(self):
        item = _item()
        assert selected_profile(item) == "tech-news"

    def test_selected_profile_none_when_absent(self):
        item = _item()
        item["processing"]["classification"]["profile"] = None
        assert selected_profile(item) is None

    def test_map_item_mints_namespaced_id_over_colon_opaque_id(self):
        # Already-colon-containing opaque Horizon IDs are NOT treated as
        # pre-namespaced: the horizon: prefix is prepended unconditionally.
        row = map_item(_item(item_id="weird:id with:colons/and-symbols"))
        assert row["id"] == "horizon:weird:id with:colons/and-symbols"

    def test_map_item_namespaces_plain_id(self):
        assert map_item(_item(item_id="github:repo:xyz"))["id"] == (
            "horizon:github:repo:xyz"
        )

    def test_mint_asset_id_never_re_derives(self):
        assert mint_asset_id("a:b:c") == "horizon:a:b:c"
        assert mint_asset_id("plain") == "horizon:plain"

    def test_map_item_position_derived_from_order(self):
        row = map_item(_item())
        blocks = row["artifacts"][0]["blocks"]
        assert [b["position"] for b in blocks] == [0, 1]
        assert blocks[0]["is_primary"] is True

    def test_map_item_languages_open_ended(self):
        item = _item()
        item["processing"]["artifacts"]["fr"] = {"title": "Titre", "blocks": []}
        row = map_item(item)
        assert {a["language"] for a in row["artifacts"]} == {"zh", "fr"}

    def test_map_item_tags_normalized_unique_sorted(self):
        row = map_item(_item())
        assert row["tags"] == ["mcp", "tool-use"]


class TestSummary:
    def test_summary_is_one_line_name_plus_json(self):
        line = summary("run", {"run_id": "r", "status": "success"})
        assert line.startswith("run: ")
        payload = json.loads(line[len("run: ") :])
        assert payload == {"run_id": "r", "status": "success"}

    def test_exit_codes_are_stable(self):
        assert (ExitCode.OK, ExitCode.GENERIC_FAILURE, ExitCode.USAGE) == (0, 1, 2)
        assert (ExitCode.HORIZON_FAILURE, ExitCode.TIMEOUT, ExitCode.PARTIAL) == (3, 4, 5)


class TestLifecycleCommands:
    def test_serve_declares_mode(self, capsys):
        cli.main(["serve"])
        payload = json.loads(capsys.readouterr().out.strip()[len("serve: ") :])
        assert payload == {"mode": "mcp-sqlite", "host": "127.0.0.1", "port": 5051}
    def test_export_summary(self, capsys):
        cli.main(["export"])
        payload = json.loads(capsys.readouterr().out.strip()[len("export: ") :])
        assert payload["format"] == "jsonl"
        assert payload["item_count"] == 0
    def test_backup_summary(self, capsys):
        cli.main(["backup"])
        payload = json.loads(capsys.readouterr().out.strip()[len("backup: ") :])
        assert payload["consistent"] is True
        assert "path" in payload
    def test_restore_dry_run_restores_nothing(self, capsys):
        cli.main(["restore", "knowledge/backups/kb.sqlite", "--dry-run"])
        payload = json.loads(capsys.readouterr().out.strip()[len("restore: ") :])
        assert payload == {
            "path": "knowledge/backups/kb.sqlite",
            "restored": False,
            "dry_run": True,
            "item_count": 0,
        }


class TestUsage:
    def test_missing_command_is_usage_error(self, capsys):
        with pytest.raises(SystemExit) as excinfo:
            cli.main([])
        assert excinfo.value.code == ExitCode.USAGE

