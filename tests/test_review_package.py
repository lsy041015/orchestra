#!/usr/bin/env python3
"""review-package writes one task's whole commit range, or refuses a bogus one."""
from pathlib import Path
import shutil
import os
import subprocess
import tempfile
import unittest

# Search PATH like a shell: on Windows a bare "bash" can resolve to WSL's
# System32\bash.exe before Git Bash.
BASH = shutil.which("bash") or "bash"

SCRIPT = Path(__file__).resolve().parents[1] / "skills/subagent-driven-development/scripts/review-package"


class ReviewPackageTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix="review-package-")
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name) / "repo"
        self.root.mkdir()
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        self.base = self.commit("plan.md", "baseline")

    def git(self, *args):
        return subprocess.run(["git", "-C", str(self.root), "-c", "user.name=Fixture",
                               "-c", "user.email=fixture@example.invalid", *args],
                              check=True, capture_output=True, text=True, encoding="utf-8").stdout.strip()

    def commit(self, name, message):
        (self.root / name).write_text(f"content of {name}\n", encoding="utf-8")
        self.git("add", name)
        self.git("commit", "-q", "-m", message)
        return self.git("rev-parse", "HEAD")

    def run_script(self, *args):
        return subprocess.run([BASH, str(SCRIPT), "plan.md", *args], cwd=self.root,
                              capture_output=True, text=True, encoding="utf-8")

    def test_package_holds_every_commit_of_the_range(self):
        self.commit("a.txt", "first step")
        head = self.commit("b.txt", "second step")
        result = self.run_script(self.base, head)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertRegex(result.stdout, r"^wrote .*: 2 commit\(s\), \d+ bytes\n$")
        name = f"review-{self.git('rev-parse', '--short', self.base)}..{self.git('rev-parse', '--short', head)}.diff"
        package = (self.root / ".orchestra/sdd/plan" / name).read_text(encoding="utf-8")
        for text in ("## Commits", "first step", "second step", "## Files changed", "## Diff",
                     "+++ b/a.txt", "+++ b/b.txt"):
            self.assertIn(text, package)

    def test_bogus_ranges_are_refused(self):
        head = self.commit("a.txt", "task work")
        self.git("checkout", "-q", "-b", "other", self.base)
        sibling = self.commit("b.txt", "other branch")
        for args, code in (((head, head), 3), ((head, sibling), 3), (("no-such-ref", head), 2),
                           (("--output=x", head), 2), ((self.base, "-x"), 2)):
            with self.subTest(args=args):
                result = self.run_script(*args)
                self.assertEqual(result.returncode, code, result.stdout + result.stderr)
                self.assertEqual(result.stdout, "")
        self.assertFalse((self.root / ".orchestra").exists())

    @unittest.skipIf(os.name == "nt", "POSIX shell command")
    def test_configured_external_diff_and_textconv_are_not_run(self):
        marker = Path(self.root).parent / "ran"
        self.git("config", "diff.external", f"touch {marker}; true")
        self.git("config", "diff.evil.textconv", f"touch {marker}; cat")
        (self.root / ".gitattributes").write_text("*.txt diff=evil\n", encoding="utf-8")
        self.git("add", ".gitattributes")
        head = self.commit("a.txt", "task work")
        self.assertEqual(self.run_script(self.base, head).returncode, 0)
        self.assertFalse(marker.exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
