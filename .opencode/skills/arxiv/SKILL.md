---
name: arxiv
description: When you need to collect latest CS/AI papers from arXiv
---

# arXiv 采集技能

## 触发场景

当用户要求采集 arXiv 上 CS/AI 类别最新论文时，自动激活此技能。

## 关键经验

- **必须设置 User-Agent 头**：arXiv 会拒绝无 User-Agent 或默认 curl 的请求，导致返回空 body。使用 `Mozilla/5.0` 或自定义 agent。
- **XML 命名空间**：返回的是 Atom feed，必须带 `atom:` 前缀或传入 `{'atom': 'http://www.w3.org/2005/Atom'}` 命名空间解析。
- **请求超时**：建议 30 秒；若 body 为空则按错误处理重试。
- **ID 提取**：`<id>` 节点文本格式为 `http://arxiv.org/abs/2604.28186`，用正则 `arxiv\.org/abs/([\d\.v]+)` 提取。

## 快速执行脚本

以下脚本可直接复制运行，输出到 `knowledge/raw/arxiv-csai-{YYYY-MM-DD}.json`：

```python
import urllib.request
import xml.etree.ElementTree as ET
import json
import re
import os
import time
from datetime import datetime, timezone


def collect_arxiv_csai(target_date=None, max_results=50):
    """
    采集 arXiv cs.AI / cs.CL / cs.LG / cs.IR 最新论文。
    target_date: 'YYYY-MM-DD' 或 None（自动使用今天）
    """
    if target_date is None:
        target_date = datetime.now(timezone.utc).strftime('%Y-%m-%d')

    url = (
        "http://export.arxiv.org/api/query?"
        "search_query=cat:cs.AI+OR+cat:cs.CL+OR+cat:cs.LG+OR+cat:cs.IR"
        f"&sortBy=submittedDate&sortOrder=descending&max_results={max_results}"
    )

    req = urllib.request.Request(
        url,
        headers={'User-Agent': 'Mozilla/5.0 (compatible; AI-KB/1.0)'}
    )

    data = b''
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = resp.read()
            if len(data) > 0:
                break
        except Exception as e:
            if attempt == 2:
                raise RuntimeError(f"arXiv API 请求失败: {e}")
            time.sleep(5 * (attempt + 1))

    root = ET.fromstring(data)
    ns = {'atom': 'http://www.w3.org/2005/Atom'}
    entries = root.findall('atom:entry', ns)

    exclude_keywords = ['quantum', 'astrophysics', 'bioinformatics', 'cryptography', 'hardware']
    items = []

    for entry in entries:
        title = entry.find('atom:title', ns)
        summary = entry.find('atom:summary', ns)
        published = entry.find('atom:published', ns)
        id_elem = entry.find('atom:id', ns)

        if title is None or summary is None:
            continue

        title_text = (title.text or "").strip()
        summary_text = (summary.text or "").strip()

        if not summary_text:
            continue

        combined = (title_text + " " + summary_text).lower()
        if any(kw in combined for kw in exclude_keywords):
            continue

        arxiv_id = ""
        if id_elem is not None and id_elem.text:
            m = re.search(r'arxiv\.org/abs/([\d\.v]+)', id_elem.text)
            if m:
                arxiv_id = m.group(1)

        pub_date = ""
        if published is not None and published.text:
            pub_date = published.text[:10]
        # 如需仅保留目标日期，取消下行注释：
        # if pub_date != target_date:
        #     continue

        authors = []
        for author in entry.findall('atom:author', ns):
            name = author.find('atom:name', ns)
            if name is not None and name.text:
                authors.append(name.text)

        cat_elem = entry.find('atom:category', ns)
        primary_cat = cat_elem.get('term') if cat_elem is not None else ''
        categories = [c.get('term') for c in entry.findall('atom:category', ns) if c.get('term')]

        items.append({
            "id": f"arxiv-{arxiv_id}",
            "title": title_text,
            "url": f"https://arxiv.org/abs/{arxiv_id}" if arxiv_id else "",
            "description": summary_text,
            "authors": authors,
            "published_at": pub_date,
            "primary_category": primary_cat,
            "categories": categories,
            "pdf_url": f"https://arxiv.org/pdf/{arxiv_id}.pdf" if arxiv_id else ""
        })

    output = {
        "source": "arxiv",
        "collected_at": datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
        "query": "cat:cs.AI+OR+cat:cs.CL+OR+cat:cs.LG+OR+cat:cs.IR",
        "count": len(items),
        "items": items
    }

    os.makedirs("knowledge/raw", exist_ok=True)
    filepath = f"knowledge/raw/arxiv-csai-{target_date}.json"
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    return filepath, items


if __name__ == "__main__":
    filepath, items = collect_arxiv_csai()
    print(f"已保存 {len(items)} 条到 {filepath}")
```

## 过滤规则

- 仅保留目标日期当天的论文（arXiv API 返回的是最近提交，可能跨天）。
- 摘要不为空（无摘要的论文通常质量较低或尚未完整发布）。
- 排除明显非 AI 的论文（标题或摘要不含 `quantum`、`astrophysics`、`bioinformatics`、`cryptography`、`hardware` 等关键词）。

## 增强信息（可选）

对当日提交量 Top 5 的论文，额外获取 PDF 的前 2 页文本存入 `pdf_excerpt` 字段，用于后续 Analyzer 生成更准确的摘要。

获取方式：

```
GET https://arxiv.org/pdf/{arxiv_id}.pdf
```

提取前 2000 字符作为 `pdf_excerpt`。

## 错误处理

| 错误 | 处理方式 |
|------|----------|
| HTTP 429 (rate limit) | 等待 10 秒后重试，最多 3 次 |
| XML 解析失败 | 跳过该条目，记录错误，继续后续 |
| 网络超时 / 空 body | 等待 5 秒后重试，最多 3 次；每次必须带 User-Agent |
| 单日无论文返回 | 报告日期可能有误，检查是否为未来日期或节假日 |
| 全量获取失败 | 返回空数组，并将错误写入 `knowledge/raw/errors-{date}.json` |

## 质量标准

- 采集条目数：10-30 条为正常范围
- 少于 5 条：arXiv 当日提交量低，放宽类别范围后重试
- 多于 50 条：过滤条件可能太宽松，收紧日期范围或排除非 AI 关键词
