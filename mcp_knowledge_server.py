#!/usr/bin/env python3
"""
MCP server for searching and reading local knowledge-base articles.

Tools:
  - search_articles: search article titles and summaries by keyword
  - get_article: fetch one article by ID
  - knowledge_stats: summarize the local knowledge base

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

import glob
import json
import os
import sys
from collections import Counter
from typing import Any

ARTICLES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "knowledge", "articles")


def load_articles() -> dict[str, dict[str, Any]]:
    """Load article JSON files and skip index.json."""
    articles: dict[str, dict[str, Any]] = {}
    pattern = os.path.join(ARTICLES_DIR, "*.json")
    for filepath in sorted(glob.glob(pattern)):
        basename = os.path.basename(filepath)
        if basename == "index.json":
            continue
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            aid = data.get("id")
            if aid:
                articles[aid] = data
                articles[aid]["_file"] = basename
        except (json.JSONDecodeError, OSError):
            continue
    return articles


def match_keyword(keyword: str, article: dict[str, Any]) -> bool:
    """Return whether keyword matches the title or summary case-insensitively."""
    kw = keyword.lower()
    fields = [article.get("title", ""), article.get("summary", "")]
    return any(kw in str(f).lower() for f in fields)


def search_articles(keyword: str, limit: int = 5) -> str:
    articles = load_articles()
    scored: list[tuple[float, dict[str, Any]]] = []
    kw = keyword.lower()

    for article in articles.values():
        if not match_keyword(keyword, article):
            continue

        score = 0
        title = article.get("title", "").lower()
        summary = article.get("summary", "").lower()
        if kw in title:
            score += 10
        if kw in summary:
            score += 3
        score += article.get("relevance_score", 0) * 2
        scored.append((score, article))

    scored.sort(key=lambda x: x[0], reverse=True)
    results = scored[:limit]

    lines: list[str] = []
    for _, article in results:
        lines.append(
            f"■ {article['title']}  (id: {article['id']}, source: {article.get('source','?')})"
        )
        lines.append(f"  Tags: {', '.join(article.get('tags', []))}")
        lines.append(f"  Summary: {article.get('summary', 'N/A')}")
        lines.append(f"  Relevance: {article.get('relevance_score', 'N/A')}")
        lines.append("")

    return "\n".join(lines).strip() if lines else f"No articles found for '{keyword}'"


def get_article(article_id: str) -> str:
    articles = load_articles()
    article = articles.get(article_id)
    if not article:
        return f"Article '{article_id}' not found."

    fields = [
        ("id", article.get("id")),
        ("title", article.get("title")),
        ("source", article.get("source")),
        ("source_url", article.get("source_url", article.get("url"))),
        ("collected_at", article.get("collected_at")),
        ("analyzed_at", article.get("analyzed_at")),
        ("status", article.get("status")),
        ("summary", article.get("summary")),
        ("tags", ", ".join(article.get("tags", []))),
        ("relevance_score", str(article.get("relevance_score", "N/A"))),
        ("stars", str(article.get("stars", "N/A"))),
        ("forks", str(article.get("forks", "N/A"))),
        ("language", article.get("language", "N/A")),
        ("description", article.get("description", "")),
    ]

    score_breakdown = article.get("score_breakdown")
    if score_breakdown:
        fields.extend([
            ("score_tech_depth", str(score_breakdown.get("tech_depth", "N/A"))),
            ("score_practical_value", str(score_breakdown.get("practical_value", "N/A"))),
            ("score_timeliness", str(score_breakdown.get("timeliness", "N/A"))),
            ("score_community_heat", str(score_breakdown.get("community_heat", "N/A"))),
            ("score_domain_match", str(score_breakdown.get("domain_match", "N/A"))),
        ])

    out: list[str] = []
    for k, v in fields:
        if v is not None and v != "":
            out.append(f"{k}: {v}")
    return "\n".join(out)


def knowledge_stats() -> str:
    articles = load_articles()
    total = len(articles)

    source_counter = Counter()
    tag_counter = Counter()
    scores = []

    for article in articles.values():
        source_counter[article.get("source", "unknown")] += 1
        for tag in article.get("tags", []):
            tag_counter[tag] += 1
        relevance_score = article.get("relevance_score")
        if relevance_score is not None:
            scores.append(relevance_score)

    lines = [
        f"Total articles: {total}",
        "",
        "Source distribution:",
    ]
    for src, cnt in source_counter.most_common():
        lines.append(f"  {src}: {cnt}")
    lines.append("")
    lines.append("Top tags:")
    for tag, cnt in tag_counter.most_common(10):
        lines.append(f"  {tag}: {cnt}")
    lines.append("")
    if scores:
        avg = sum(scores) / len(scores)
        lines.append(f"Average relevance score: {avg:.2f}")
        lines.append(f"Score range: {min(scores):.2f} - {max(scores):.2f}")

    return "\n".join(lines)


TOOLS = [
    {
        "name": "search_articles",
        "description": "按关键词搜索本地知识库中的文章标题和摘要，返回匹配结果列表",
        "inputSchema": {
            "type": "object",
            "properties": {
                "keyword": {"type": "string", "description": "搜索关键词"},
                "limit": {"type": "integer", "description": "返回结果数量上限，默认 5"},
            },
            "required": ["keyword"],
        },
    },
    {
        "name": "get_article",
        "description": "按文章 ID 获取完整信息",
        "inputSchema": {
            "type": "object",
            "properties": {
                "article_id": {"type": "string", "description": "文章 ID"},
            },
            "required": ["article_id"],
        },
    },
    {
        "name": "knowledge_stats",
        "description": "返回知识库统计信息：文章总数、来源分布、热门标签",
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
    params = msg.get("params", {})

    if method == "initialize":
        send_response(rpc_id, {
            "protocolVersion": "2024-11-05",
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "knowledge-mcp", "version": "1.0.0"},
        })
        return

    if method == "notifications/initialized":
        return

    if method == "tools/list":
        send_response(rpc_id, {"tools": TOOLS})
        return

    if method == "tools/call":
        tool_name = params.get("name", "")
        arguments = params.get("arguments", {})

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
