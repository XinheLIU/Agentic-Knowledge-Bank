"""KB-owned asset mapping checks, split from the provider transport suite."""
from __future__ import annotations

import json
import pytest
from kb.horizon.contract import mint_asset_id
from kb.horizon.mapper import (
    METADATA_MAX_BYTES, MappingFailure, map_content_item, required_field_failure,
)
from kb.model import ReasonCode

pytestmark = pytest.mark.non_llm

def _content_item(**extra) -> dict:
    base = {
        "id": "github:repo:xyz",
        "source_type": "github",
        "title": "A Horizon item",
        "url": "https://example.com/x",
        "author": None,
        "published_at": "2026-09-11T08:00:00+00:00",
        "fetched_at": "2026-09-11T09:00:00+00:00",
        "content": "main body",
        "comments": "some comments",
        "profile": ["tech-news"],
        "processing": {
            "classification": {
                "profile": "tech-news", "method": "ai_match",
                "confidence": 0.9, "reason": "matches P0",
            },
            "analysis": {
                "score": 8, "reason": "relevant", "summary": "有用的摘要",
                "tags": ["mcp", "tool-use", "mcp"],
            },
            "artifacts": {
                "zh": {"title": "深入", "blocks": [
                    {"id": "b1", "title": "块", "content": "内容",
                     "source_refs": ["s1"], "primary": True},
                    {"id": "b2", "title": "块二", "content": "内容二",
                     "source_refs": [], "primary": False},
                ]},
                "fr": {"title": "Résumé", "blocks": []},
            },
        },
        "metadata": {"stars": 42},
        "brand_new_upstream_field": {"nested": {"deep": [1, 2, 3]}},
    }
    base.update(extra)
    return base

def test_mapper_mints_opaque_namespaced_id():
    mapped = map_content_item(_content_item())
    assert mapped["id"] == "horizon:github:repo:xyz"
    assert mapped["id"] == mint_asset_id("github:repo:xyz")
    # Already-colon-containing input is not treated as pre-namespaced.
    assert map_content_item(_content_item(id="horizon:already"))["id"] == "horizon:horizon:already"

def test_mapper_derives_profile_from_classification_not_routing_hint():
    mapped = map_content_item(_content_item())
    assert mapped["profile"] == "tech-news"
    assert mapped["profile_method"] == "ai_match"
    assert mapped["profile_confidence"] == 0.9
    assert mapped["profile_reason"] == "matches P0"

def test_mapper_preserves_open_ended_languages_and_block_position():
    mapped = map_content_item(_content_item())
    languages = [a["language"] for a in mapped["artifacts"]]
    assert languages == ["zh", "fr"]  # fr is not a "known" language; open-ended
    zh = mapped["artifacts"][0]
    assert [b["position"] for b in zh["blocks"]] == [0, 1]  # derived from list order
    assert zh["blocks"][0]["is_primary"] is True
    assert zh["blocks"][0]["source_ids"] == ["s1"]

def test_mapper_language_filter_keeps_only_requested():
    mapped = map_content_item(_content_item(), languages=["fr"])
    assert [a["language"] for a in mapped["artifacts"]] == ["fr"]

def test_mapper_bounded_metadata_preserves_unknown_fields():
    mapped = map_content_item(_content_item())
    extras = mapped["horizon_extra"]
    assert extras["brand_new_upstream_field"]["nested"]["deep"] == [1, 2, 3]
    # Explicitly mapped keys are not duplicated into the bounded blob.
    assert "processing" not in extras and "metadata" not in extras
    assert mapped["metadata_json"] == {"stars": 42}

def test_mapper_bounded_metadata_size_and_depth_caps():
    huge = _content_item(big_blob={"k" * 100: "v" * (METADATA_MAX_BYTES * 4)})
    mapped = map_content_item(huge)
    blob = json.dumps(mapped["horizon_extra"], ensure_ascii=False, default=str)
    # Bounded: the preserved blob stays under the cap, never a row bomb.
    assert len(blob.encode("utf-8")) <= METADATA_MAX_BYTES
    # Depth cap: a beyond-max-depth structure is dropped (its emptiness
    # collapses upward), while a shallow sibling field survives.
    deep = _content_item(
        deep={"a": {"b": {"c": {"d": {"e": {"f": {"g": 1}}}}}}},
        shallow="kept",
    )
    extras = map_content_item(deep)["horizon_extra"]
    assert extras["shallow"] == "kept"
    assert "deep" not in extras

def test_mapper_missing_required_fields_fail_auditably():
    for field in ("title", "url", "published_at"):
        item = _content_item()
        del item[field]
        with pytest.raises(MappingFailure) as excinfo:
            map_content_item(item)
        assert excinfo.value.reason == f"missing required field {field!r}"
        assert excinfo.value.item_id == "github:repo:xyz"
        assert ReasonCode.is_registered(excinfo.value.reason_code)
        assert excinfo.value.reason_code == "MAP_FAILED"

def test_mapper_missing_id_fails_without_item_id():
    item = _content_item()
    del item["id"]
    with pytest.raises(MappingFailure) as excinfo:
        map_content_item(item)
    assert excinfo.value.item_id is None

def test_mapper_empty_required_string_fails():
    with pytest.raises(MappingFailure, match="published_at"):
        map_content_item(_content_item(published_at="  "))

def test_required_field_failure_carries_registered_code():
    failure = required_field_failure("some-id", "published_at")
    assert failure.reason_code == "MAP_FAILED"
    assert ReasonCode.is_registered(failure.reason_code)

def test_mapper_failure_code_not_in_registry_raises():
    with pytest.raises(ValueError, match="registry"):
        MappingFailure("id", "reason", reason_code="NOT_A_CODE")

def test_mapper_tags_deduped_and_sorted():
    mapped = map_content_item(_content_item())
    assert mapped["tags"] == ["mcp", "tool-use"]

def test_mapper_non_object_capture_fails():
    with pytest.raises(MappingFailure, match="not a JSON object"):
        map_content_item(["not", "a", "dict"])  # type: ignore[arg-type]
