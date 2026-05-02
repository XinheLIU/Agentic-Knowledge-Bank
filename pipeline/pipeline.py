"""
Four-step AI knowledge-base pipeline: collect, analyze, organize, and save.

Usage:
    python3 pipeline/pipeline.py --sources github,rss --limit 20
    python3 pipeline/pipeline.py --sources github --limit 5 --dry-run
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv

# Keep direct script execution working by importing sibling modules from this directory.
sys.path.insert(0, str(Path(__file__).parent))
from model_client import chat_with_retry, create_provider, estimate_cost
from rss_reader import collect_rss  # noqa: F401 - re-exported for compatibility.

load_dotenv()
logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).parent.parent
RAW_DIR = PROJECT_ROOT / "knowledge" / "raw"
ARTICLES_DIR = PROJECT_ROOT / "knowledge" / "articles"


def collect_github(limit: int = 10) -> list[dict[str, Any]]:
    """
    Collect popular AI-related repositories from the GitHub Search API.

    Args:
        limit: Maximum number of repositories to collect.

    Returns:
        Raw repository records.
    """
    token = os.getenv("GITHUB_TOKEN", "")
    headers = {"Accept": "application/vnd.github.v3+json"}
    if token:
        headers["Authorization"] = f"token {token}"

    one_week_ago = (datetime.now(timezone.utc) - timedelta(days=7)).strftime("%Y-%m-%d")
    query = f"ai agent llm stars:>100 pushed:>{one_week_ago}"
    url = "https://api.github.com/search/repositories"
    params = {
        "q": query,
        "sort": "stars",
        "order": "desc",
        "per_page": min(limit, 30),
    }

    results: list[dict[str, Any]] = []
    try:
        with httpx.Client(timeout=30.0) as client:
            resp = client.get(url, params=params, headers=headers)
            resp.raise_for_status()
            data = resp.json()

            for i, repo in enumerate(data.get("items", [])[:limit]):
                now = datetime.now(timezone.utc).isoformat()
                results.append({
                    "id": f"github-{datetime.now().strftime('%Y%m%d')}-{i+1:03d}",
                    "title": repo["full_name"],
                    "source": "github",
                    "source_url": repo["html_url"],
                    "author": repo["owner"]["login"],
                    "published_at": repo.get("pushed_at", ""),
                    "raw_description": repo.get("description", "") or "",
                    "stars": repo.get("stargazers_count", 0),
                    "language": repo.get("language", ""),
                    "topics": repo.get("topics", []),
                    "collected_at": now,
                })

        logger.info("GitHub 采集完成: %d 条", len(results))
    except httpx.HTTPError as e:
        logger.error("GitHub API 调用失败: %s", e)

    return results


# collect_rss lives in pipeline/rss_reader.py and is re-exported here for old imports.


def step_collect(sources: list[str], limit: int) -> list[dict[str, Any]]:
    """
    Step 1: collect raw data from the requested sources.

    Args:
        sources: Source names such as ["github", "rss"].
        limit: Maximum number of items per source.

    Returns:
        Combined raw records.
    """
    print(f"\n{'='*60}")
    print(f"📥 Step 1: 采集（sources={sources}, limit={limit}）")
    print(f"{'='*60}")

    all_items: list[dict[str, Any]] = []

    if "github" in sources:
        all_items.extend(collect_github(limit))
    if "rss" in sources:
        all_items.extend(collect_rss(limit))

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    raw_file = RAW_DIR / f"raw_{timestamp}.json"
    with open(raw_file, "w", encoding="utf-8") as f:
        json.dump(all_items, f, ensure_ascii=False, indent=2)

    print(f"  采集到 {len(all_items)} 条原始数据")
    print(f"  保存到 {raw_file}")

    return all_items


ANALYZE_PROMPT_TEMPLATE = """请分析以下 AI 技术内容，返回 JSON 格式的分析结果。

内容信息：
- 标题：{title}
- 来源：{source}
- 描述：{description}

请返回以下格式的 JSON（不要包含 markdown 代码块标记）：
{{
  "summary": "2-3 句话的技术摘要，说明核心内容和价值",
  "score": 7,
  "tags": ["tag1", "tag2"],
  "audience": "intermediate"
}}

评分标准（1-10）：
- 9-10: 突破性创新
- 7-8: 优秀技术分享
- 5-6: 普通有用信息
- 3-4: 内容较浅
- 1-2: 低质量

可用标签：agent, rag, mcp, llm, fine-tuning, prompt-engineering, multi-agent,
tool-use, evaluation, deployment, security, reasoning, code-generation, vision, audio

audience 可选值：beginner, intermediate, advanced"""


def step_analyze(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Step 2: analyze each item with the configured LLM.

    Args:
        items: Raw records.

    Returns:
        Records enriched with analysis fields.
    """
    print(f"\n{'='*60}")
    print(f"🔍 Step 2: 分析（{len(items)} 条内容）")
    print(f"{'='*60}")

    provider = create_provider()
    analyzed: list[dict[str, Any]] = []
    total_cost = 0.0

    try:
        for i, item in enumerate(items):
            print(f"  [{i+1}/{len(items)}] 分析: {item['title'][:50]}...")

            prompt = ANALYZE_PROMPT_TEMPLATE.format(
                title=item["title"],
                source=item["source"],
                description=item.get("raw_description", "无描述"),
            )

            try:
                response = chat_with_retry(
                    provider,
                    messages=[
                        {"role": "system", "content": "你是一个 AI 技术分析专家。请严格按要求返回 JSON。"},
                        {"role": "user", "content": prompt},
                    ],
                    temperature=0.3,
                    max_tokens=500,
                )

                cost = estimate_cost(provider.model, response.usage)
                total_cost += cost

                content = response.content.strip()
                content = re.sub(r"^```json\s*", "", content)
                content = re.sub(r"\s*```$", "", content)

                analysis = json.loads(content)

                enriched = {**item, **analysis}
                enriched["status"] = "review"
                enriched["analyzed_at"] = datetime.now(timezone.utc).isoformat()
                analyzed.append(enriched)

            except (json.JSONDecodeError, KeyError) as e:
                logger.warning("分析结果解析失败: %s — %s", item["title"], e)
                enriched = {
                    **item,
                    "summary": item.get("raw_description", "")[:200],
                    "score": 5,
                    "tags": ["llm"],
                    "audience": "intermediate",
                    "status": "draft",
                    "analyzed_at": datetime.now(timezone.utc).isoformat(),
                }
                analyzed.append(enriched)

    finally:
        provider.close()

    print(f"  分析完成: {len(analyzed)} 条")
    print(f"  估算总成本: ${total_cost:.6f}")

    return analyzed


def step_organize(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Step 3: deduplicate and normalize analyzed records.

    Args:
        items: Analyzed records.

    Returns:
        Normalized article records.
    """
    print(f"\n{'='*60}")
    print(f"📋 Step 3: 整理（{len(items)} 条内容）")
    print(f"{'='*60}")

    seen_urls: set[str] = set()
    unique: list[dict[str, Any]] = []

    if ARTICLES_DIR.exists():
        for f in ARTICLES_DIR.glob("*.json"):
            try:
                with open(f, "r", encoding="utf-8") as fh:
                    existing = json.load(fh)
                    if "source_url" in existing:
                        seen_urls.add(existing["source_url"])
            except (json.JSONDecodeError, IOError):
                pass

    dedup_count = 0
    for item in items:
        url = item.get("source_url", "")
        if url in seen_urls:
            dedup_count += 1
            continue
        seen_urls.add(url)
        unique.append(item)

    organized: list[dict[str, Any]] = []
    for item in unique:
        article = {
            "id": item.get("id", "unknown-000"),
            "title": item.get("title", ""),
            "source": item.get("source", "unknown"),
            "source_url": item.get("source_url", ""),
            "author": item.get("author", "unknown"),
            "published_at": item.get("published_at", ""),
            "collected_at": item.get("collected_at", ""),
            "summary": item.get("summary", ""),
            "score": max(1, min(10, item.get("score", 5))),
            "tags": item.get("tags", []),
            "audience": item.get("audience", "intermediate"),
            "status": item.get("status", "draft"),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        organized.append(article)

    print(f"  去重: 移除 {dedup_count} 条重复")
    print(f"  整理后: {len(organized)} 条")

    return organized


def step_save(items: list[dict[str, Any]], dry_run: bool = False) -> list[Path]:
    """
    Step 4: save each article as a standalone JSON file.

    Args:
        items: Normalized articles.
        dry_run: Print target paths without writing files.

    Returns:
        Target file paths.
    """
    print(f"\n{'='*60}")
    print(f"💾 Step 4: 保存（{len(items)} 条内容，dry_run={dry_run}）")
    print(f"{'='*60}")

    ARTICLES_DIR.mkdir(parents=True, exist_ok=True)
    saved_files: list[Path] = []

    for item in items:
        filename = f"{item['id']}.json"
        filepath = ARTICLES_DIR / filename

        if dry_run:
            print(f"  [DRY RUN] 将保存: {filepath}")
        else:
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(item, f, ensure_ascii=False, indent=2)
            print(f"  已保存: {filepath}")

        saved_files.append(filepath)

    print(f"\n  共 {'模拟' if dry_run else ''}保存 {len(saved_files)} 个文件")
    return saved_files


def run_pipeline(
    sources: list[str],
    limit: int = 20,
    dry_run: bool = False,
    steps: list[int] | None = None,
) -> dict[str, Any]:
    """
    Run the requested pipeline steps.

    Args:
        sources: Source names.
        limit: Maximum number of items per source.
        dry_run: Print target paths without writing files.
        steps: Step numbers to run; defaults to all steps.

    Returns:
        Pipeline run statistics.
    """
    run_steps = set(steps) if steps else {1, 2, 3, 4}

    start_time = datetime.now()
    print(f"\n{'#'*60}")
    print(f"# AI 知识库流水线 — {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"# 数据源: {', '.join(sources)} | 限制: {limit} | DryRun: {dry_run}")
    print(f"# 执行步骤: {sorted(run_steps)}")
    print(f"{'#'*60}")

    raw_items: list[dict] = []
    analyzed_items: list[dict] = []
    organized_items: list[dict] = []
    saved_files: list[str] = []

    if 1 in run_steps:
        raw_items = step_collect(sources, limit)
        if not raw_items:
            print("\n⚠️  没有采集到任何数据，流水线结束。")
            return {"collected": 0, "analyzed": 0, "saved": 0}

    if 2 in run_steps and raw_items:
        analyzed_items = step_analyze(raw_items)

    if 3 in run_steps and analyzed_items:
        organized_items = step_organize(analyzed_items)

    if 4 in run_steps and organized_items:
        saved_files = step_save(organized_items, dry_run=dry_run)

    elapsed = (datetime.now() - start_time).total_seconds()
    stats = {
        "collected": len(raw_items),
        "analyzed": len(analyzed_items),
        "organized": len(organized_items),
        "saved": len(saved_files),
        "elapsed_seconds": round(elapsed, 1),
        "dry_run": dry_run,
    }

    print(f"\n{'#'*60}")
    print(f"# 流水线完成！耗时 {elapsed:.1f} 秒")
    print(f"# 采集: {stats['collected']} → 分析: {stats['analyzed']} "
          f"→ 整理: {stats['organized']} → 保存: {stats['saved']}")
    print(f"{'#'*60}\n")

    return stats


def main() -> None:
    parser = argparse.ArgumentParser(
        description="AI 知识库采集流水线",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
    python3 pipeline/pipeline.py --sources github,rss --limit 20
    python3 pipeline/pipeline.py --sources github --limit 5 --dry-run
    python3 pipeline/pipeline.py --sources rss --limit 10
        """,
    )
    parser.add_argument(
        "--sources",
        type=str,
        default="github,rss",
        help="数据源，逗号分隔（默认: github,rss）",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=20,
        help="每个源的最大采集数量（默认: 20）",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="仅模拟运行，不实际保存文件",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="显示详细日志",
    )
    parser.add_argument(
        "--step",
        type=int,
        action="append",
        help="指定执行的步骤（1-4），可多次使用，如 --step 1 --step 2",
    )
    parser.add_argument(
        "--provider",
        type=str,
        default=None,
        help="LLM 提供商（deepseek/qwen/openai），覆盖环境变量 LLM_PROVIDER",
    )

    args = parser.parse_args()

    if args.provider:
        os.environ["LLM_PROVIDER"] = args.provider

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    sources = [s.strip() for s in args.sources.split(",")]
    run_pipeline(
        sources=sources,
        limit=args.limit,
        dry_run=args.dry_run,
        steps=args.step,
    )


if __name__ == "__main__":
    main()
