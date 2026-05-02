---
name: hackernews
description: When you need to collect Hacker News top stories in AI/LLM/Agent domains
---

# Hacker News 采集技能

## 触发场景

当用户要求采集 Hacker News 上与 AI/LLM/Agent 相关的热门文章或项目时，自动激活此技能。

## 关键经验

- **限制批量 ID 数量**：Firebase API 需要逐个请求 item 详情。为避免脚本超时，建议只拉取前 **60-80** 个 top story ID（而非 100+）。
- **显式超时**：每个 item 请求必须设 `timeout=10`，否则偶发挂起会导致整体脚本超时。
- **请求间隔**：建议 80-100ms，避免触发限流。
- **反噪关键词**：通用词如 `model` 容易误匹配非 AI 新闻（如 Apple 硬件供应），必须设置 **anti_noise** 黑名单直接丢弃。

## 快速执行脚本

以下脚本可直接复制运行，输出到 `knowledge/raw/hackernews-top-{YYYY-MM-DD}.json`：

```python
import urllib.request
import json
import time
import os
from datetime import datetime, timezone


def collect_hackernews_ai(limit_ids=60, min_score=10):
    # 1. 获取 Top Stories ID 列表
    with urllib.request.urlopen(
        "https://hacker-news.firebaseio.com/v0/topstories.json", timeout=30
    ) as resp:
        all_ids = json.loads(resp.read())

    ids = all_ids[:limit_ids]

    include_keywords = [
        'ai ', 'llm', 'large language model', 'gpt', 'claude',
        'agent', 'agentic', 'rag ', 'mcp', 'model context protocol',
        'openai', 'anthropic', 'deepseek', 'neural', 'transformer',
        'inference', 'fine-tuning', 'machine learning', 'pytorch',
        'tensorflow', 'diffusion', 'multimodal', 'embedding',
        'reasoning model'
    ]

    # 即使命中 include_keywords，只要命中 anti_noise 就丢弃
    anti_noise = [
        'mac studio', 'mac mini', 'nhs ', 'laliga', 'ip blockage',
        'port numbers', 'short supply', 'spain\'s parliament',
        'constrained for months'
    ]

    items = []
    for item_id in ids:
        try:
            url = f"https://hacker-news.firebaseio.com/v0/item/{item_id}.json"
            with urllib.request.urlopen(url, timeout=10) as resp:
                data = json.loads(resp.read())

            if not data or data.get('type') != 'story':
                continue
            if data.get('deleted') or data.get('dead'):
                continue

            score = data.get('score', 0)
            if score < min_score:
                continue

            title = data.get('title', '').lower()
            url_text = data.get('url', '').lower()

            if any(k in title for k in anti_noise):
                continue

            if not any(k in title or k in url_text for k in include_keywords):
                continue

            posted_at = ""
            if data.get('time'):
                posted_at = datetime.fromtimestamp(
                    data['time'], tz=timezone.utc
                ).strftime('%Y-%m-%dT%H:%M:%SZ')

            items.append({
                "id": f"hn-{data['id']}",
                "title": data['title'],
                "url": data.get('url', f"https://news.ycombinator.com/item?id={data['id']}"),
                "description": "",
                "points": score,
                "comments_count": data.get('descendants', 0),
                "posted_at": posted_at,
                "author": data.get('by', ''),
                "hn_id": data['id'],
                "is_github_project": 'github.com' in (data.get('url') or '')
            })
        except Exception:
            pass
        time.sleep(0.08)

    today = datetime.now(timezone.utc).strftime('%Y-%m-%d')
    output = {
        "source": "hackernews",
        "collected_at": datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
        "query": "topstories",
        "count": len(items),
        "items": items
    }

    os.makedirs("knowledge/raw", exist_ok=True)
    filepath = f"knowledge/raw/hackernews-top-{today}.json"
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    return filepath, items


if __name__ == "__main__":
    filepath, items = collect_hackernews_ai()
    print(f"已保存 {len(items)} 条到 {filepath}")
```

## 过滤规则

- 类型必须为 `"story"`（过滤 `job`、`poll`、`comment`）。
- 排除已删除或死亡的条目（`deleted: true` 或 `dead: true`）。
- 必须有标题和 URL。
- **AI 相关性过滤**：标题（或 URL）包含 `include_keywords` 之一（不区分大小写）。
- **反噪过滤**：标题命中 `anti_noise` 的条目直接丢弃，避免硬件供应、体育版权等非 AI 新闻混入。
- 热度 >= 10 分（`score >= 10`）。

## 输出格式

- 文件路径：`knowledge/raw/hackernews-top-{YYYY-MM-DD}.json`
- 顶层包含 `source`, `collected_at`, `query`, `count`, `items`
- 使用 2 空格缩进

顶层结构示例：

```json
{
  "source": "hackernews",
  "collected_at": "2026-05-01T12:00:00Z",
  "query": "topstories",
  "count": 12,
  "items": [
    {
      "id": "hn-42424242",
      "title": "Show HN: My AI Project",
      "url": "https://example.com/project",
      "description": "",
      "points": 256,
      "comments_count": 42,
      "posted_at": "2026-04-29T06:00:00Z",
      "author": "username",
      "hn_id": 42424242,
      "is_github_project": false
    }
  ]
}
```

## 错误处理

| 错误 | 处理方式 |
|------|----------|
| Firebase API 连接超时 | 等待 1 秒后重试，最多 3 次 |
| 单条 item 获取失败 | 跳过该条目，记录错误，继续后续 |
| 频繁请求触发限流 | 增加请求间隔至 500ms，最多重试 3 次 |
| 全量获取失败 | 返回空数组，并将错误写入 `knowledge/raw/errors-{date}.json` |

## 质量标准

- 采集条目数：10-20 条为正常范围（取前 60-80 个 ID 时）
- 少于 8 条：AI 相关内容较少，放宽关键词或检查 anti_noise 是否过严
- 多于 30 条：可能未充分过滤，检查 AI 相关性条件是否太宽松
