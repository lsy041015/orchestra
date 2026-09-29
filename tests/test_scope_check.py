#!/usr/bin/env python3
"""The scope check the main session runs around a Claude worker."""
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
CHECK = ROOT / "skills/orchestrator/scripts/scope-check.mjs"


def git(repo, *args):
    return subprocess.run(["git", "-C", str(repo), "-c", "user.name=Fixture",
                           "-c", "user.email=fixture@example.invalid", *args],
                          check=True, capture_output=True, text=True, encoding="utf-8")


class ScopeCheckTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix="scope-check-")
        self.addCleanup(temp.cleanup)
        self.temp = Path(temp.name)
        self.repo = self.temp / "repo"
        self.repo.mkdir()
        subprocess.run(["git", "init", "-q", str(self.repo)], check=True)
        (self.repo / "keep.txt").write_text("keep\n", encoding="utf-8")
        git(self.repo, "add", ".")
        git(self.repo, "commit", "-q", "-m", "baseline")
        self.state = self.temp / "scope.json"

    def check(self, command, cwd=None, allowed=None):
        args = ["node", str(CHECK), command, "--cwd", str(cwd or self.repo), "--state", str(self.state)]
        if allowed:
            args += ["--allowed", allowed]
        return subprocess.run(args, capture_output=True, text=True, encoding="utf-8")

    def test_flags_only_files_outside_the_allowed_list(self):
        self.assertEqual(self.check("before").stdout, "Scope: baseline recorded\n")
        (self.repo / "a.txt").write_text("a\n", encoding="utf-8")
        result = self.check("after", allowed="a.txt")
        self.assertEqual((result.returncode, result.stdout), (0, "Scope: ok\n"), result.stderr)
        (self.repo / "b.txt").write_text("b\n", encoding="utf-8")
        result = self.check("after", allowed="a.txt")
        self.assertEqual((result.returncode, result.stdout), (1, "Scope: outside allowed: b.txt\n"))

    def test_committed_change_still_counts(self):
        # Claude workers may commit, and a committed file leaves git status clean.
        self.check("before")
        (self.repo / "b.txt").write_text("b\n", encoding="utf-8")
        git(self.repo, "add", "b.txt")
        git(self.repo, "commit", "-q", "-m", "worker commit")
        result = self.check("after", allowed="a.txt")
        self.assertEqual(result.stdout, "Scope: outside allowed: b.txt\n", result.stderr)

    def test_baseline_from_another_checkout_is_unchecked(self):
        other = self.temp / "other"
        other.mkdir()
        subprocess.run(["git", "init", "-q", str(other)], check=True)
        self.check("before", cwd=other)
        result = self.check("after", allowed="a.txt")
        self.assertEqual(result.returncode, 1)
        self.assertTrue(result.stdout.startswith("Scope: unchecked (the baseline is for "), result.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=2)
