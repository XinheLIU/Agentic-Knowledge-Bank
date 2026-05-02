#!/usr/bin/env python3
"""
知识库 MCP Server — 让 AI 工具通过 MCP 搜索和查询本地知识库文章。

提供 3 个工具：
  - search_articles: 按关键词搜索文章
  - get_article: 按 ID 获取文章详情
  - knowledge_stats: 查看知识库统计信息

运行方式：
    python3 mcp_knowledge_server.py

配置到 OpenCode（opencode.json）：
    {
      "mcpServers": {
        "knowledge": {
          "command": "python3",
          "args": ["mcp_knowledge_server.py"]
        }
      }
    }
"""
import json
import sys
import os
import glob
import re
from collections import Counter

ARTICLES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "knowledge", "articles")


def load_articles():
    """加载 knowledge/articles/ 下所有 JSON（跳过 index.json）。"""
    articles = {}
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


def match_keyword(keyword, article):
    """检查关键词是否匹配标题或摘要（大小写不敏感）。"""
    kw = keyword.lower()
    fields = [article.get("title", ""), article.get("summary", "")]
    return any(kw in str(f).lower() for f in fields)


def search_articles(keyword, limit=5):
    articles = load_articles()
    scored = []
    for aid, art in articles.items():
        if match_keyword(keyword, art):
            score = 0
            title = art.get("title", "").lower()
            summary = art.get("summary", "").lower()
            kw = keyword.lower()
            if kw in title:
                score += 10
            if kw in summary:
                score += 3
            score += art.get("relevance_score", 0) * 2
            scored.append((score, art))

    scored.sort(key=lambda x: x[0], reverse=True)
    results = scored[:limit]

    lines = []
    for _, art in results:
        lines.append(f"■ {art['title']}  (id: {art['id']}, source: {art.get('source','?')})")
        lines.append(f"  Tags: {', '.join(art.get('tags', []))}")
        lines.append(f"  Summary: {art.get('summary', 'N/A')}")
        lines.append(f"  Relevance: {art.get('relevance_score', 'N/A')}")
        lines.append("")

    return "\n".join(lines).strip() if lines else f"No articles found for '{keyword}'"


def get_article(article_id):
    articles = load_articles()
    art = articles.get(article_id)
    if not art:
        return f"Article '{article_id}' not found."

    fields = [
        ("id", art.get("id")),
        ("title", art.get("title")),
        ("source", art.get("source")),
        ("source_url", art.get("source_url", art.get("url"))),
        ("collected_at", art.get("collected_at")),
        ("analyzed_at", art.get("analyzed_at")),
        ("status", art.get("status")),
        ("summary", art.get("summary")),
        ("tags", ", ".join(art.get("tags", []))),
        ("relevance_score", str(art.get("relevance_score", "N/A"))),
        ("stars", str(art.get("stars", "N/A"))),
        ("forks", str(art.get("forks", "N/A"))),
        ("language", art.get("language", "N/A")),
        ("description", art.get("description", "")),
    ]

    score_breakdown = art.get("score_breakdown")
    if score_breakdown:
        sb = score_breakdown
        fields.append(("score_tech_depth", str(sb.get("tech_depth", "N/A"))))
        fields.append(("score_practical_value", str(sb.get("practical_value", "N/A"))))
        fields.append(("score_timeliness", str(sb.get("timeliness", "N/A"))))
        fields.append(("score_community_heat", str(sb.get("community_heat", "N/A"))))
        fields.append(("score_domain_match", str(sb.get("domain_match", "N/A"))))

    out = []
    for k, v in fields:
        if v is not None and v != "":
            out.append(f"{k}: {v}")
    return "\n".join(out)


def knowledge_stats():
    articles = load_articles()
    total = len(articles)

    source_counter = Counter()
    tag_counter = Counter()
    scores = []

    for art in articles.values():
        source_counter[art.get("source", "unknown")] += 1
        for t in art.get("tags", []):
            tag_counter[t] += 1
        rs = art.get("relevance_score")
        if rs is not None:
            scores.append(rs)

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


def send_response(rpc_id, result):
    resp = {"jsonrpc": "2.0", "id": rpc_id, "result": result}
    sys.stdout.write(json.dumps(resp, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def send_error(rpc_id, code, message):
    resp = {"jsonrpc": "2.0", "id": rpc_id, "error": {"code": code, "message": message}}
    sys.stdout.write(json.dumps(resp, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def send_tool_result(rpc_id, text):
    content = [{"type": "text", "text": text}]
    send_response(rpc_id, {"content": content})


def handle_message(msg):
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


def main():
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
