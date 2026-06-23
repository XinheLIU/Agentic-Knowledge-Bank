"""Daily digest: email a ranked summary of the day's high-priority articles.

Standalone CLI (not a graph node) that reads ``knowledge/articles/*.json`` after
a run — the same "index is a derived artifact, built after the workflow" shape as
``scripts/build_index``. It exists because the pipeline otherwise only commits
JSON to git and has no way to *reach* the user.

The SMTP mechanics are borrowed from the retired Info-Sentinel-Agent
(``src/notifier.py``), stripped to the stdlib (no markdown2 — short digests send
fine as plain text). When SMTP env is missing the CLI prints the digest and
exits 0, so an unconfigured CI run is a graceful no-op.
"""

from __future__ import annotations

import argparse
import json
import os
import smtplib
from datetime import datetime, timezone
from email.mime.text import MIMEText
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ARTICLES_DIR = PROJECT_ROOT / "knowledge" / "articles"

DEFAULT_PRIORITIES = ("study-now", "save-for-context")
PRIORITY_HEADINGS = {
    "study-now": "## Study now",
    "save-for-context": "## Save for context",
    "skim": "## Skim",
    "low-priority": "## Low priority",
    "skip": "## Skip",
}


def _load_articles(articles_dir: Path) -> list[dict[str, Any]]:
    articles: list[dict[str, Any]] = []
    if not articles_dir.exists():
        return articles
    for path in articles_dir.glob("*.json"):
        if path.name in ("index.json", "_skipped.jsonl"):
            continue
        try:
            articles.append(json.loads(path.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, OSError):
            continue
    return articles


def _collected_date(article: dict[str, Any]) -> str:
    """Return the YYYY-MM-DD portion of collected_at, or '' if unparseable."""
    raw = str(article.get("collected_at", ""))
    return raw[:10] if len(raw) >= 10 else ""


def _render_item(article: dict[str, Any]) -> str:
    title = article.get("title", "(untitled)")
    url = article.get("source_url") or article.get("url", "")
    lines = [f"### [{title}]({url})" if url else f"### {title}"]

    summary = str(article.get("summary", "")).strip()
    if summary:
        lines.append(summary)

    insight = str(article.get("key_insight", "")).strip()
    if insight:
        lines.append(f"**洞察:** {insight}")

    meta_bits = []
    track = article.get("learning_track")
    if track and track != "background":
        meta_bits.append(f"track: {track}")
    tags = article.get("learning_tags") or []
    if tags:
        meta_bits.append("tags: " + ", ".join(tags))
    action = article.get("suggested_action")
    if action:
        meta_bits.append(f"action: {action}")
    score = article.get("priority_score")
    if score is not None:
        meta_bits.append(f"score: {score}")
    if meta_bits:
        lines.append("_" + " · ".join(meta_bits) + "_")

    return "\n\n".join(lines)


def build_digest(
    articles_dir: Path = ARTICLES_DIR,
    since: str | None = None,
    priorities: tuple[str, ...] = DEFAULT_PRIORITIES,
) -> str:
    """Render a markdown digest of articles collected on ``since``.

    ``since`` defaults to the current UTC date. Items are filtered to
    ``reading_priority in priorities``, grouped by priority, and sorted by
    ``priority_score`` descending within each group. An empty result still
    returns a valid (short) body.
    """
    day = since or datetime.now(timezone.utc).strftime("%Y-%m-%d")

    selected = [
        a
        for a in _load_articles(articles_dir)
        if _collected_date(a) == day and a.get("reading_priority") in priorities
    ]
    selected.sort(key=lambda a: a.get("priority_score", 0), reverse=True)

    header = f"# AI 知识库每日简报 · {day}"
    if not selected:
        return f"{header}\n\n今日没有高优先级条目。"

    parts = [header, f"_共 {len(selected)} 条高优先级_"]
    for priority in priorities:
        group = [a for a in selected if a.get("reading_priority") == priority]
        if not group:
            continue
        parts.append(PRIORITY_HEADINGS.get(priority, f"## {priority}"))
        parts.extend(_render_item(a) for a in group)

    return "\n\n".join(parts)


def _smtp_settings() -> dict[str, Any]:
    return {
        "host": os.getenv("SMTP_HOST", "smtp.gmail.com"),
        "port": int(os.getenv("SMTP_PORT", "587")),
        "email": os.getenv("EMAIL_ADDRESS", ""),
        "password": os.getenv("EMAIL_PASSWORD", ""),
        "recipients": os.getenv("DIGEST_RECIPIENTS", ""),
    }


def send_email(subject: str, body: str, settings: dict[str, Any]) -> bool:
    """Send ``body`` as a plain-text email. Returns True if sent.

    Skips (returns False) when sender credentials are missing, so callers can
    treat an unconfigured environment as a no-op.
    """
    email = settings.get("email")
    password = settings.get("password")
    if not email or not password:
        print("[Digest] 未配置 EMAIL_ADDRESS/EMAIL_PASSWORD，跳过发送")
        return False

    recipients_raw = settings.get("recipients") or email
    recipients = [r.strip() for r in str(recipients_raw).split(",") if r.strip()]

    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = email
    msg["To"] = ", ".join(recipients)

    with smtplib.SMTP(settings["host"], settings["port"]) as server:
        server.starttls()
        server.login(email, password)
        server.send_message(msg)

    print(f"[Digest] 已发送至 {len(recipients)} 个收件人")
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description="AI-KB daily digest email")
    parser.add_argument("--since", default=None, help="YYYY-MM-DD (default: UTC today)")
    parser.add_argument("--articles-dir", default=None, help="Override articles directory")
    parser.add_argument(
        "--stdout",
        action="store_true",
        help="Print the digest instead of sending email",
    )
    args = parser.parse_args()

    articles_dir = Path(args.articles_dir) if args.articles_dir else ARTICLES_DIR
    day = args.since or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    body = build_digest(articles_dir=articles_dir, since=args.since)

    settings = _smtp_settings()
    if args.stdout or not (settings["email"] and settings["password"]):
        print(body)
        return

    send_email(subject=f"AI 知识库每日简报 · {day}", body=body, settings=settings)


if __name__ == "__main__":
    main()
