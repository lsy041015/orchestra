#!/usr/bin/env python3
"""find-polluter.sh never reports "all clean" when it could not check."""
from pathlib import Path
import json
import shutil
import subprocess
import tempfile
import unittest

# Search PATH like a shell: on Windows a bare "bash" can resolve to WSL's
# System32\bash.exe before Git Bash.
BASH = shutil.which("bash") or "bash"

SCRIPT = Path(__file__).resolve().parents[1] / "skills/systematic-debugging/find-polluter.sh"


class FindPolluterTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix="find-polluter-")
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        (self.root / "package.json").write_text(
            json.dumps({"private": True, "scripts": {"test": "node"}}), encoding="utf-8")
        (self.root / "clean.test.js").write_text("", encoding="utf-8")
        # A name with a space must stay one file.
        (self.root / "dirty one.test.js").write_text(
            "require('fs').writeFileSync('polluted', 'x');", encoding="utf-8")

    def run_script(self):
        # Through `bash -c` so the pattern stays quoted: MSYS bash globs a bare
        # `*` in its own Windows command line before the script sees it.
        return subprocess.run([BASH, "-c", '"$0" polluted "*.test.js"', str(SCRIPT)], cwd=self.root,
                              capture_output=True, text=True, encoding="utf-8", timeout=120)

    def test_finds_polluter_whose_name_has_a_space(self):
        result = self.run_script()
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("dirty one.test.js", result.stdout)

    def test_existing_pollution_is_an_error_not_clean(self):
        (self.root / "polluted").write_text("x", encoding="utf-8")
        result = self.run_script()
        self.assertEqual(result.returncode, 2, result.stdout)
        self.assertNotIn("all tests clean", result.stdout)

    def test_project_without_test_script_is_an_error_not_clean(self):
        (self.root / "package.json").unlink()
        result = self.run_script()
        self.assertEqual(result.returncode, 2, result.stdout)
        self.assertNotIn("all tests clean", result.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=2)
