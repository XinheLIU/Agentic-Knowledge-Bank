"""Ticket 16 — retirement manifest for the legacy LangGraph/JSON production path.

Locks in that the retired production entrypoints, hooks, and source config are
gone, that no production module imports them or accesses ``knowledge/articles``
directly, that no duplicate vocabulary remains outside the canonical owners
(O2), and that the retired contradictory ID validator (G1) is not kept alive.

Retained on purpose (NOT retired):
- ``tests/fixtures/legacy_articles/`` — sanitized fixture corpus + oracles.
- ``kb/admission/hollow_words.py`` — canonical hollow-word lists (policy §4).
- ``kb/admission/patterns.py`` / ``kb/admission/policy.py`` — canonical vocab.
- ``docs/`` history, ``CHANGELOG.md``, ticket files — historical references.
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = pytest.mark.non_llm

REPO_ROOT = Path(__file__).resolve().parent.parent

RETIRED_PATHS = [
    # LangGraph workflow package
    "workflows",
    # legacy JSON validation / quality hooks
    "hooks",
    # legacy index rebuild + backfill entrypoints
    "scripts/build_index.py",
    "scripts/backfill_scores.py",
    # retired prompts, source config, and externalized prompt templates
    "prompts",
    # legacy LangGraph demo notebook
    "notebooks/langgraph_workflow_demo.ipynb",
    # OpenCode write-hook wired to the retired hooks
    ".opencode/plugins/validate.ts",
    # retired collector/LLM env template
    ".env.example",
    # legacy-only CI lane
    ".github/workflows/llm-e2e.yml",
]

FORBIDDEN_IMPORT_TOKENS = (
    "workflows.graph",
    "workflows.analyzer",
    "workflows.collector",
    "workflows.reviewer",
    "workflows.reviser",
    "workflows.organizer",
    "workflows.planner",
    "workflows.human_flag",
    "workflows.model_client",
    "workflows.prompts",
    "workflows.digest",
    "workflows.relevance_profile",
    "workflows.skipped",
    "workflows.state",
    "from workflows",
    "import workflows",
    "from hooks",
    "import hooks",
    "from check_quality import",
    "from validate_json import",
    "import check_quality",
    "import validate_json",
)

#: Comment-only mentions of the retired framework (kept out of imports) are
#: tolerated; topical vocabulary strings (e.g. the ``langgraph`` learning tag
#: in the canonical admission policy) are not retired symbols.
_COMMENT_MENTIONS_OK = ("langgraph",)

#: Modules that must never re-declare admission/reason vocabulary (O2) or run a
#: parallel JSON pipeline against ``knowledge/articles/``.
PRODUCTION_MODULES = [
    *sorted(str(p.relative_to(REPO_ROOT)) for p in (REPO_ROOT / "kb").rglob("*.py") if "__pycache__" not in p.parts),
    "mcp_knowledge_server.py",
    "ui/app.py",
    *sorted(str(p) for p in (REPO_ROOT / "scripts").glob("*.py")),
]

#: Retained fixtures whose identity strings must all satisfy the canonical rule.
CANONICAL_ID_OK = r"^[a-z0-9][a-z0-9:._-]*$"


class TestRetiredPathsAbsent:
    @pytest.mark.parametrize("rel", RETIRED_PATHS)
    def test_retired_path_is_gone(self, rel):
        assert not (REPO_ROOT / rel).exists(), f"retired path still present: {rel}"

    def test_no_stray_workflows_or_hooks_leftovers(self):
        assert not (REPO_ROOT / "workflows").exists()
        assert not (REPO_ROOT / "hooks").exists()


class TestNoProductionImports:
    @pytest.mark.parametrize("rel", PRODUCTION_MODULES)
    def test_no_retired_module_references(self, rel):
        text = (REPO_ROOT / rel).read_text(encoding="utf-8")
        lowered = text.lower()
        for token in FORBIDDEN_IMPORT_TOKENS:
            assert token not in lowered, f"{rel} references retired symbol {token!r}"
        assert "import langgraph" not in lowered
        assert "from langgraph" not in lowered

    def test_collection_workflow_is_owned_by_information_assistant(self):
        assert not (REPO_ROOT / ".github" / "workflows" / "daily-collect.yml").exists()


class TestHorizonRunSurfaceOwnedElsewhere:
    """The KB-side Horizon *run* surface belongs to the collection owner.

    KB keeps asset identity, mapping, admission and storage. It must not run
    the provider, own a transport, or expose a collection entry point; those
    live in ``agent-tools`` (provider plumbing) and Information Assistant
    (orchestration, scheduling, digests).
    """

    KB_SIDE_RUN_PATHS = [
        "kb/horizon/adapter.py",
        "kb/horizon/transport.py",
        "kb/horizon/source_config.py",
        "scripts/production_run.py",
        "scripts/setup_horizon.py",
    ]

    @pytest.mark.parametrize("rel", KB_SIDE_RUN_PATHS)
    def test_kb_side_run_surface_is_gone(self, rel):
        assert not (REPO_ROOT / rel).exists(), f"KB-side run surface still present: {rel}"

    def test_kb_ingest_admits_payloads_without_running_the_provider(self):
        text = (REPO_ROOT / "kb" / "ingest.py").read_text(encoding="utf-8")
        assert "ingest_horizon_run" not in text
        assert "HorizonTransport" not in text
        assert "from kb.horizon.transport" not in text

    def test_kb_cli_does_not_expose_a_collection_command(self):
        text = (REPO_ROOT / "kb" / "cli.py").read_text(encoding="utf-8")
        assert "subprocess" not in text
        assert "Information commands moved to" not in text

    def test_no_production_module_imports_removed_kb_shims(self):
        offenders = []
        for rel in PRODUCTION_MODULES:
            path = REPO_ROOT / rel
            if not path.exists():
                continue
            text = path.read_text(encoding="utf-8")
            if "kb.horizon.transport" in text or "kb.horizon.source_config" in text:
                offenders.append(rel)
        assert offenders == [], f"stale KB-side shim imports: {offenders}"

    def test_pyproject_has_no_langgraph_dependency(self):
        text = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
        assert "langgraph" not in text.lower()
        assert "feedparser" not in text.lower()
        assert '"workflows"' not in text
        assert '"hooks"' not in text


class TestNoDirectArticlesAccess:
    def test_production_modules_do_not_reference_knowledge_articles(self):
        offenders = []
        for rel in PRODUCTION_MODULES:
            text = (REPO_ROOT / rel).read_text(encoding="utf-8")
            if "knowledge/articles" in text:
                offenders.append(rel)
        assert offenders == [], f"direct legacy corpus access: {offenders}"


class TestCanonicalVocabularyO2:
    """O2: reason codes/enums live only in kb/model.py + kb/admission/policy.py."""

    def test_no_duplicate_hollow_word_list_outside_canonical_owner(self):
        canonical = (REPO_ROOT / "kb" / "admission" / "hollow_words.py").read_text(encoding="utf-8")
        probe = canonical.split()[0]  # arbitrary non-trivial token guard
        assert probe
        for rel in PRODUCTION_MODULES:
            if rel.endswith("hollow_words.py"):
                continue
            text = (REPO_ROOT / rel).read_text(encoding="utf-8").lower()
            assert "hollow" not in text or "hollow_words" in text, rel

    def test_no_parallel_json_pipeline_modules(self):
        """The organizer/reviewer vocabulary classes died with the package."""
        for rel in PRODUCTION_MODULES:
            text = (REPO_ROOT / rel).read_text(encoding="utf-8")
            assert "personal_fit_score" not in text or rel.startswith("tests/"), rel


class TestG1ValidatorGone:
    """G1 is closed by deletion, not migration: no contradictory ID rule survives."""

    def test_legacy_validator_module_is_not_importable(self):
        sys_path_saved = list(__import__("sys").path)
        __import__("sys").path.insert(0, str(REPO_ROOT))
        try:
            for name in ("validate_json", "check_quality"):
                with pytest.raises(ImportError):
                    __import__(name)
                assert name not in __import__("sys").modules
        finally:
            __import__("sys").path[:] = sys_path_saved

    def test_fixture_ids_satisfy_canonical_rule_only(self):
        import re

        canonical = re.compile(CANONICAL_ID_OK)
        fixture_root = REPO_ROOT / "tests" / "fixtures" / "legacy_articles" / "articles"
        ids = [p.stem for p in fixture_root.glob("*.json")]
        assert ids, "retained fixture corpus must not be empty"
        for ident in ids:
            assert canonical.match(ident), ident
