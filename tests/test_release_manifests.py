#!/usr/bin/env python3
"""A release keeps every version marker in step."""
from pathlib import Path
import json
import unittest

ROOT = Path(__file__).resolve().parents[1]


def load(path):
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


class ReleaseManifestTests(unittest.TestCase):
    def test_versions_agree(self):
        version = load(".claude-plugin/plugin.json")["version"]
        self.assertEqual(load(".codex-plugin/plugin.json")["version"], version)
        # Both hosts install from this ref, so it must name the released tag, not a moving branch.
        for marketplace in (".agents/plugins/marketplace.json", ".claude-plugin/marketplace.json"):
            with self.subTest(marketplace=marketplace):
                source = load(marketplace)["plugins"][0]["source"]
                self.assertEqual(source["ref"], f"v{version}")
        self.assertIn(f"## [{version}]", (ROOT / "CHANGELOG.md").read_text(encoding="utf-8"))
        for readme in ("README.md", "README.en.md"):
            with self.subTest(readme=readme):
                self.assertIn(f"v{version}", (ROOT / readme).read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
