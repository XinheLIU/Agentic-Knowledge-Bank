"""Ticket 17 — project memory / documentation / version metadata manifest.

Locks in that every *maintained* Markdown document describes the current KB
boundary and its split owners, carries a non-stale ``Last updated`` date,
contains no dead ``openspec/`` links, references no deleted runnable path, and
that all visible version literals agree with the single version source
(``pyproject.toml`` → ``kb.store.model.project_version()``).

Preserved on purpose (NOT scanned for staleness): ``docs/archive/`` historical
audits, ``docs/product/ai-kb/product.html`` (durable PRD), ``.scratch/`` effort
tickets (historical record of what was true when written), ``TODO.md``
(user-authored), ``tests/fixtures/`` legacy corpus oracles, and vendored
scaffolding (``.opencode/``, ``.claude/``, ``.codex/`` skills).
"""

from __future__ import annotations

import datetime
import re
from pathlib import Path

import pytest

pytestmark = pytest.mark.non_llm

REPO_ROOT = Path(__file__).resolve().parent.parent

#: Floor for ``Last updated`` markers. The workspace guide bumps a document's
#: date only when that document is actually changed, so maintained docs
#: legitimately carry different dates; asserting one common "today" would force
#: rewrites of files that were not edited. A floor still catches markers that
#: silently regress to a pre-migration date.
MIN_DOC_DATE = "2026-09-13"

#: Maintained docs that must describe the current system and carry an accurate
#: ``Last updated`` marker. Historical/labelled docs are deliberately excluded.
MAINTAINED_DOCS = [
    "AGENTS.md",
    "README.md",
    "README.zh-CN.md",
    "CHANGELOG.md",
    "project-vision.md",
    "CONTEXT.md",
    "docs/agents/memory.md",
    "docs/adr/0001-radar-minted-immutable-item-ids.md",
    "docs/product/ai-kb/design.md",
    "docs/product/ai-kb/admission-policy.md",
    "docs/product/ai-kb/asset-audit-model.md",
    "ui/README.md",
]

#: Deleted runnable legacy paths that maintained docs must not present as
#: runnable/recommended. Historical *retirement* mentions (e.g. "已在 ticket 16
#: 退役") are allowed via the escape clause below.
DEAD_RUNNABLE_PATHS = [
    "openspec/",
    "workflows/digest.py",
    "workflows/relevance_profile.yaml",
    "workflows/rss_sources.yaml",
    "scripts/build_index.py",
    "scripts/backfill_scores.py",
    "hooks/check_quality.py",
    "hooks/validate_json.py",
    # moved out of KB with the Horizon-run eviction (collection owner's instead)
    "kb/horizon/adapter.py",
    "kb/horizon/transport.py",
    "kb/horizon/source_config.py",
    "scripts/production_run.py",
    "scripts/setup_horizon.py",
]

#: A mention is stale unless the sentence marks the path as deleted/retired.
RETIREMENT_MARKERS = (
    "退役",
    "废止",
    "已删除",
    "已随 ticket 16",
    "已重写并移至",
    "was removed",
    "removed entirely",
    "retired",
    "deleted",
    "died with",
    "no longer",
    "不再",
    "not re-pointed",
    "die with",
)  # noqa: RUF027 - intentionally unclosed tuple below; see RETIREMENT_MARKERS definition

#: Version literals in maintained docs must reference the declared version or
#: carry one of these historical escapes.
HISTORICAL_VERSION_OK = ("0.7.0",)  # declared version itself

_LAST_UPDATED = re.compile(r"最后更新|Last [Uu]pdated")


def _is_retirement_mention(line: str) -> bool:
    return any(marker in line for marker in RETIREMENT_MARKERS)


#: Historical release-note sections describe the pipeline as it was; the
#: changelog is exempt from the runnable-path scan below the cutover divider.
CHANGELOG_HISTORICAL_OK = ("CHANGELOG.md",)


def _declared_version() -> str:
    text = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    match = re.search(r'^version\s*=\s*"([^"]+)"', text, re.MULTILINE)
    assert match, "pyproject.toml must declare a version"
    return match.group(1)


class TestLastUpdatedMetadata:
    @pytest.mark.parametrize("rel", MAINTAINED_DOCS)
    def test_has_last_updated_line(self, rel):
        text = (REPO_ROOT / rel).read_text(encoding="utf-8")
        assert _LAST_UPDATED.search(text), f"{rel} lacks a Last updated marker"

    @pytest.mark.parametrize("rel", MAINTAINED_DOCS)
    def test_last_updated_is_not_stale(self, rel):
        text = (REPO_ROOT / rel).read_text(encoding="utf-8")
        dates = re.findall(r"(?:Last [Uu]pdated|最后更新)[:：]\s*(\d{4}-\d{2}-\d{2})", text)
        assert dates, f"{rel} lacks a dated Last updated marker"
        floor = datetime.date.fromisoformat(MIN_DOC_DATE)
        for value in dates:
            parsed = datetime.date.fromisoformat(value)  # ISO-parseable
            assert parsed >= floor, (
                f"{rel} Last updated {value} predates the {MIN_DOC_DATE} migration baseline"
            )


class TestNoDeadOpenspecLinks:
    def test_no_openspec_links_in_maintained_docs(self):
        offenders = []
        for rel in MAINTAINED_DOCS:
            text = (REPO_ROOT / rel).read_text(encoding="utf-8")
            if "openspec" in text.lower():
                offenders.append(rel)
        assert offenders == [], f"maintained docs still reference openspec: {offenders}"

    def test_archive_navigation_points_at_current_docs(self):
        text = (REPO_ROOT / "docs" / "archive" / "README.md").read_text(encoding="utf-8")
        assert "openspec" not in text.lower()
        assert "../../README.md" in text
        assert "../../AGENTS.md" in text


class TestNoDeadRunnablePaths:
    @pytest.mark.parametrize("rel", MAINTAINED_DOCS)
    def test_no_stale_legacy_path_presented_as_runnable(self, rel):
        if rel in CHANGELOG_HISTORICAL_OK:
            pytest.skip("historical release notes preserved verbatim (labelled history)")
        stale = []
        for line_no, line in enumerate(
            (REPO_ROOT / rel).read_text(encoding="utf-8").splitlines(), 1
        ):
            for path in DEAD_RUNNABLE_PATHS:
                if path in line and not _is_retirement_mention(line):
                    stale.append(f"{rel}:{line_no}: {path}")
        assert stale == [], f"stale runnable-path references: {stale}"

    def test_maintained_docs_do_not_recommend_legacy_commands(self):
        forbidden_commands = (
            "python -m workflows",
            "python workflows/",
            "uv run python scripts/build_index.py",
            "uv run python scripts/backfill_scores.py",
        )
        for rel in MAINTAINED_DOCS:
            text = (REPO_ROOT / rel).read_text(encoding="utf-8")
            for cmd in forbidden_commands:
                assert cmd not in text, f"{rel} recommends retired command {cmd!r}"

    def test_readmes_describe_current_ownership(self):
        for rel in ("README.md", "README.zh-CN.md", "AGENTS.md"):
            text = (REPO_ROOT / rel).read_text(encoding="utf-8")
            assert "Information Assistant" in text, rel
            assert "SQLite" in text, rel
            # Collection orchestration moved to the collection owner; KB docs
            # must not advertise a KB-side run entry point.
            for retired in ("ingest_horizon_run", "production_run.py", "setup_horizon.py"):
                assert retired not in text, f"{rel} advertises retired entry point {retired!r}"


class TestMemoryRoutingFacts:
    def test_memory_md_describes_full_repository(self):
        text = (REPO_ROOT / "docs" / "agents" / "memory.md").read_text(encoding="utf-8")
        lowered = text.lower()
        assert "documentation-only snapshot" not in lowered
        assert ".git` is empty" not in lowered
        assert ".git is empty" not in lowered

    def test_memory_md_names_active_effort(self):
        text = (REPO_ROOT / "docs" / "agents" / "memory.md").read_text(encoding="utf-8")
        assert "horizon-kb-design" in text
        assert "state.md" in text

    def test_memory_md_points_at_current_source(self):
        text = (REPO_ROOT / "docs" / "agents" / "memory.md").read_text(encoding="utf-8")
        assert "kb/" in text


class TestVersionAgreement:
    def test_single_declared_version_matches_project_version(self):
        from kb.store.model import project_version

        declared = _declared_version()
        assert project_version() == declared, (
            f"kb.store.model.project_version()={project_version()!r} != pyproject {declared!r}"
        )

    def test_maintained_version_literals_agree_with_declared(self):
        """Every explicit version literal in maintained docs must equal the
        declared version (with or without ``v``/backticks). Historical version
        sections live only in CHANGELOG.md, which is excluded here."""
        declared = _declared_version()
        pattern = re.compile(r"`?v?\b(\d+\.\d+\.\d+)\b`?")
        allowed_non_project_versions = {
            "docs/agents/memory.md": {"0.1.1"},  # PRD revision number, not project version
            "docs/product/ai-kb/admission-policy.md": {"0.1.0"},  # policy revision, not project version
            "docs/product/ai-kb/asset-audit-model.md": {"0.1.0"},  # policy revision example, not project version
        }
        for rel in MAINTAINED_DOCS:
            if rel == "CHANGELOG.md":
                continue
            text = (REPO_ROOT / rel).read_text(encoding="utf-8")
            for match in pattern.finditer(text):
                literal = match.group(0)
                if match.group(1) == declared:
                    continue
                if match.group(1) in allowed_non_project_versions.get(rel, set()):
                    continue
                pytest.fail(
                    f"{rel} mentions version literal {literal!r} which disagrees "
                    f"with the declared version {declared!r}"
                )
