"""Synthetic render regressions; never use instance data as repository fixtures."""
from __future__ import annotations

import base64
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


CHECKER = Path(__file__).resolve().parents[1] / "skills/knowledge/llm-wiki-lint/scripts/check-assets.mjs"
MARKED = os.environ.get("MARKED_MODULE")
PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jRZkAAAAASUVORK5CYII="
)


@unittest.skipUnless(MARKED, "set MARKED_MODULE to an existing marked.esm.js; no installs")
class AssetCheckTests(unittest.TestCase):
    def test_rendering_and_file_validation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "notes").mkdir()
            (root / "wiki").mkdir()
            (root / "image name.png").write_bytes(PNG)
            (root / "image#one.png").write_bytes(PNG)
            (root / "fake.png").write_text("not an image")
            (root / "empty.png").write_bytes(b"")
            (root / "valid.svg").write_text('<svg xmlns="http://www.w3.org/2000/svg"><path d="M0 0"/></svg>')
            (root / "invalid.svg").write_text('<svg xmlns="http://www.w3.org/2000/svg"><broken></svg>')
            (root / "attachment.pdf").write_bytes(b"%PDF-synthetic")
            cases = {
                "encoded": "![alt](../image%20name.png)",
                "angle": "![alt](<../image name.png>)",
                "reference": "![alt][ref]\n\n[ref]: <../image name.png>",
                "reserved": "![alt](../image%23one.png)",
                "raw": "![alt](../image name.png)",
                "fake": "![alt](../fake.png)",
                "empty": "![alt](../empty.png)",
                "svg": "![alt](../valid.svg)",
                "badsvg": "![alt](../invalid.svg)",
                "missing": "![alt](../missing.png)",
                "alt": "![](../image%20name.png)",
                "asset": "[download](../attachment.pdf)",
                "rawasset": "[download](../image name.png)",
                "remote": "![alt](https://example.invalid/image.png)",
                "footnotes": "Claim.[^mat:m001]\n\n[^mat:m001]: `not-an-asset.md`",
                "code": "`![literal](../bad path.png)`\n\n```md\n![literal](../bad path.png)\n```",
                "escaped": r"\!\[literal\]\(../bad path.png\)",
            }
            for name, body in cases.items():
                (root / "notes" / f"{name}.md").write_text(body)
            before = {p: p.read_bytes() for p in root.rglob("*") if p.is_file()}
            result = subprocess.run(
                ["node", str(CHECKER), "--kb", str(root), "--marked", str(MARKED)],
                capture_output=True, text=True, check=False,
            )
            self.assertEqual(result.returncode, 1, result.stderr)
            report = json.loads(result.stdout)
            by_case = {Path(row["file"]).stem: row for row in report["references"]}
            for name in ["encoded", "angle", "reference", "reserved", "asset", "svg"]:
                self.assertEqual(by_case[name]["status"], "PASS", name)
            for name, reason in {
                "raw": "does-not-render", "rawasset": "does-not-render",
                "fake": "invalid-or-unsupported-image-signature", "empty": "empty-file",
                "badsvg": "invalid-or-unsupported-image-signature",
                "alt": "missing-alt",
            }.items():
                self.assertIn(reason, by_case[name]["failures"], name)
            self.assertEqual(by_case["missing"]["status"], "FAIL")
            self.assertEqual(by_case["remote"]["status"], "NOT VERIFIED")
            for name in ["footnotes", "code", "escaped"]:
                self.assertNotIn(name, by_case)
            self.assertEqual(before, {p: p.read_bytes() for p in root.rglob("*") if p.is_file()})

    def test_missing_renderer_is_not_a_pass(self) -> None:
        result = subprocess.run(
            ["node", str(CHECKER), "--kb", "/unused", "--marked", "/missing-renderer.mjs"],
            capture_output=True, text=True, check=False,
        )
        self.assertEqual(result.returncode, 2)
        self.assertEqual(json.loads(result.stderr)["status"], "NOT VERIFIED")


if __name__ == "__main__":
    unittest.main()
