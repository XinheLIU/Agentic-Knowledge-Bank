"""Notebook smoke tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

pytestmark = pytest.mark.non_llm


def test_langgraph_workflow_notebook_exists_and_is_valid_json():
    notebook = (
        Path(__file__).resolve().parent.parent
        / "notebooks"
        / "langgraph_workflow_demo.ipynb"
    )
    data = json.loads(notebook.read_text(encoding="utf-8"))
    assert data["nbformat"] == 4
    assert len(data["cells"]) >= 4
