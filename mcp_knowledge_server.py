#!/usr/bin/env python3
"""MCP server over the canonical SQLite asset store (ticket 11).

Tools (same names, arguments, and stdio JSON-RPC framing as the legacy JSON
scanner, so existing client configurations keep working):

  - search_articles: full-text search over accepted assets (FTS5 with the
    store's tested LIKE fallback; structured ``source_type`` filter through
    the reader seam, never direct SQL here).
  - get_article: one asset by canonical ID (``horizon:...`` / ``legacy:...``).
  - knowledge_stats: whole-store counters, top tags, and score summary.

Responses expose only canonical fields (G7: the legacy ``relevance_score``,
``stars``, ``forks``, ``score_breakdown``, ``analyzed_at``, and ``_file``
fields are gone). ``get_article`` renders real stored data with an explicit
``null`` marker — never ``N/A`` placeholders.

Store resolution (the only supported persistence contract):
  1. explicit ``KB_STORE_PATH`` (env var);
  2. ``KB_DATA_ROOT/kb.sqlite``; otherwise the user-local knowledge data root.

If the canonical store is absent, the server launches (compatibility) and
reports the fact explicitly through ``knowledge_stats`` and per-call errors
until ingestion creates it. It never falls back to scanning ``knowledge/``.

Usage:
    python3 mcp_knowledge_server.py

OpenCode configuration example (opencode.json):
    {
      "mcpServers": {
        "knowledge": {
          "command": "python3",
          "args": ["mcp_knowledge_server.py"]
        }
      }
    }
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

from kb.store import fts as fts_mod
from kb.store.model import AssetStore, ItemRecord, StoreStats

PROJECT_ROOT = Path(__file__).resolve().parent
from kb.paths import data_root

DEFAULT_STORE_PATH = data_root() / "kb.sqlite"
STORE_PATH_ENV = "KB_STORE_PATH"

NOT_FOUND_PREFIX = "Article"
NOT_FOUND_SUFFIX = "not found."


# ---------------------------------------------------------------------------
# Store seam: canonical store open + narrow ticket-10 compatibility wrappers
# ---------------------------------------------------------------------------


def store_path() -> Path:
    """Resolved canonical store path (``KB_STORE_PATH`` beats the default)."""
    override = os.environ.get(STORE_PATH_ENV)
    return Path(override) if override else DEFAULT_STORE_PATH


def open_store(path: Path | None = None) -> AssetStore | None:
    """Open the canonical store, or ``None`` when it does not exist yet.

    A missing file must not be created by a read-only consumer — ingestion
    (ticket 10) owns store creation. An existing file is opened and migrated
    by the store's own versioned, transactional migrations.
    """
    target = store_path() if path is None else path
    if not target.exists():
        return None
    return AssetStore.open(target)


def _utcnow() -> str:
    import time

    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def open_or_seeded_store(path: Path | None = None) -> AssetStore | None:
    """Open the canonical store (read-only consumer; no seeding)."""
    return open_store(path)


# ---------------------------------------------------------------------------
# Rendering (canonical fields only)
# ---------------------------------------------------------------------------


def format_score(score: float | None) -> str:
    """Canonical score as text; ``null`` is explicit, never ``N/A``."""
    return "null" if score is None else f"{score:g}"


def render_search_item(record: ItemRecord) -> list[str]:
    lines = [
        f"■ {record.title}  (id: {record.id}, source_type: {record.source_type})"
    ]
    tags = ", ".join(record.tags) if record.tags else "none"
    lines.append(f"  Tags: {tags}")
    lines.append(f"  Summary: {record.summary if record.summary is not None else 'null'}")
    lines.append(f"  Score: {format_score(record.score)}")
    lines.append("")
    return lines


def search_articles(keyword: str, limit: int = 5, source_type: str | None = None) -> str:
    """Search accepted assets through the store's FTS/reader seam."""
    store = open_or_seeded_store()
    if store is None:
        return (
            f"Knowledge store not initialized ({store_path()}). "
            "Run 'information-run' (Information Assistant) to collect and admit assets."
        )
    try:
        records, mode = store.search(
            keyword, source_type=source_type, limit=max(int(limit), 0)
        )
    finally:
        store.close()

    if not records:
        return f"No articles found for '{keyword}'"

    lines: list[str] = []
    for record in records:
        lines.extend(render_search_item(record))
    body = "\n".join(lines).rstrip()
    if mode == fts_mod.FTS_LIKE_FALLBACK:
        body += "\n  (served by the explicit LIKE fallback; FTS5 unavailable)"
    return body


def get_article(article_id: str) -> str:
    """One asset by canonical ID with real stored data (explicit nulls)."""
    store = open_or_seeded_store()
    if store is None:
        return (
            f"{NOT_FOUND_PREFIX} '{article_id}' {NOT_FOUND_SUFFIX} "
            f"(knowledge store not initialized at {store_path()})"
        )
    try:
        record = store.get_item(article_id)
    finally:
        store.close()
    if record is None:
        return f"{NOT_FOUND_PREFIX} '{article_id}' {NOT_FOUND_SUFFIX}"

    fields: list[tuple[str, str]] = [
        ("id", record.id),
        ("state", record.state),
        ("title", record.title),
        ("source_type", record.source_type),
        ("url", record.url),
        ("author", record.author),
        ("published_at", record.published_at),
        ("fetched_at", record.fetched_at),
        ("story_fp", record.story_fp),
        ("score", format_score(record.score)),
        ("score_reason", record.score_reason),
        ("summary", record.summary),
        ("content_main", record.content_main),
        ("tags", ", ".join(record.tags) if record.tags else None),
    ]
    out = [f"{k}: {v if v is not None else 'null'}" for k, v in fields]
    if record.superseded_by:
        out.append(f"superseded_by: {record.superseded_by}")
    return "\n".join(out)


def knowledge_stats() -> str:
    """Store counters, tag distribution, and score summary (canonical only)."""
    store = open_or_seeded_store()
    if store is None:
        return (
            f"Knowledge store not initialized ({store_path()}). "
            "Total articles: 0."
        )
    try:
        stats: StoreStats = store.stats()
        top_items = store.list_items(limit=None)
        mode = store.fts_mode()
    finally:
        store.close()

    lines = [
        f"Total articles: {stats.item_count}",
        "",
        "Store:",
        f"  Accepted assets: {stats.accepted_count}",
        f"  Superseded assets: {stats.superseded_count}",
        f"  Ingestion runs: {stats.run_count}",
        f"  Admission decisions: {stats.admission_count}",
    ]
    if mode != fts_mod.FTS_TRIGRAM:
        lines.append(f"  FTS mode: {mode} (LIKE fallback; FTS5 unavailable)")

    source_counter: dict[str, int] = {}
    tag_counter: dict[str, int] = {}
    scores: list[float] = []
    for record in top_items:
        source_counter[record.source_type] = source_counter.get(record.source_type, 0) + 1
        for tag in record.tags:
            tag_counter[tag] = tag_counter.get(tag, 0) + 1
        if record.score is not None:
            scores.append(record.score)

    if source_counter:
        lines += ["", "Source distribution:"]
        for src, cnt in sorted(source_counter.items(), key=lambda kv: (-kv[1], kv[0])):
            lines.append(f"  {src}: {cnt}")

    if tag_counter:
        lines += ["", "Top tags:"]
        top_tags = sorted(tag_counter.items(), key=lambda kv: (-kv[1], kv[0]))[:10]
        for tag, cnt in top_tags:
            lines.append(f"  {tag}: {cnt}")

    if scores:
        avg = sum(scores) / len(scores)
        lines += [
            "",
            f"Average score: {avg:.2f}",
            f"Score range: {min(scores):.2f} - {max(scores):.2f}",
        ]

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# MCP stdio JSON-RPC framing (unchanged external contract)
# ---------------------------------------------------------------------------

TOOLS = [
    {
        "name": "search_articles",
        "description": "按关键词全文检索知识库已收录资产（FTS5），返回匹配结果列表",
        "inputSchema": {
            "type": "object",
            "properties": {
                "keyword": {"type": "string", "description": "搜索关键词"},
                "limit": {
                    "type": "integer",
                    "description": "返回结果数量上限，默认 5",
                },
                "source_type": {
                    "type": "string",
                    "description": "按来源类型过滤（repository/paper/blog 等）",
                },
            },
            "required": ["keyword"],
        },
    },
    {
        "name": "get_article",
        "description": "按资产 ID 获取完整信息（canonical ID，如 horizon:... / legacy:...）",
        "inputSchema": {
            "type": "object",
            "properties": {
                "article_id": {"type": "string", "description": "资产 ID"},
            },
            "required": ["article_id"],
        },
    },
    {
        "name": "knowledge_stats",
        "description": "返回知识库统计信息：资产总数、来源分布、热门标签",
        "inputSchema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
]

HANDLERS = {
    "search_articles": search_articles,
    "get_article": get_article,
    "knowledge_stats": knowledge_stats,
}


def send_response(rpc_id: Any, result: dict[str, Any]) -> None:
    resp = {"jsonrpc": "2.0", "id": rpc_id, "result": result}
    sys.stdout.write(json.dumps(resp, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def send_error(rpc_id: Any, code: int, message: str) -> None:
    resp = {"jsonrpc": "2.0", "id": rpc_id, "error": {"code": code, "message": message}}
    sys.stdout.write(json.dumps(resp, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def send_tool_result(rpc_id: Any, text: str) -> None:
    content = [{"type": "text", "text": text}]
    send_response(rpc_id, {"content": content})


def handle_message(msg: dict[str, Any]) -> None:
    method = msg.get("method")
    rpc_id = msg.get("id")
    params = msg.get("params") or {}

    if method == "initialize":
        send_response(rpc_id, {
            "protocolVersion": "2024-11-05",
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "knowledge-mcp", "version": "2.0.0"},
        })
        return

    if method == "notifications/initialized":
        return

    if method == "tools/list":
        send_response(rpc_id, {"tools": TOOLS})
        return

    if method == "tools/call":
        tool_name = params.get("name", "")
        arguments = params.get("arguments") or {}

        if tool_name not in HANDLERS:
            send_error(rpc_id, -32601, f"Tool not found: {tool_name}")
            return

        try:
            result_text = HANDLERS[tool_name](**arguments)
            send_tool_result(rpc_id, result_text)
        except TypeError as e:
            send_error(rpc_id, -32602, f"Invalid arguments: {e}")
        except Exception as e:
            send_error(rpc_id, -32603, f"Tool execution error: {e}")
        return

    send_error(rpc_id, -32601, f"Method not found: {method}")


def main() -> None:
    while True:
        try:
            line = sys.stdin.readline()
            if not line:
                break
            line = line.strip()
            if not line:
                continue
            msg = json.loads(line)
            handle_message(msg)
        except json.JSONDecodeError:
            continue
        except KeyboardInterrupt:
            break


if __name__ == "__main__":
    main()
