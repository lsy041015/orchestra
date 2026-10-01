#!/usr/bin/env python3
"""The scope check the main session runs around a Claude worker."""
from pathlib import Path
import os
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

    def check(self, command, cwd=None, allowed=None, home=None):
        args = ["node", str(CHECK), command, "--cwd", str(cwd or self.repo), "--state", str(self.state)]
        if allowed:
            args += ["--allowed", allowed]
        env = os.environ.copy()
        if home:
            env.update(HOME=str(home), USERPROFILE=str(home))
        return subprocess.run(args, capture_output=True, text=True, encoding="utf-8", env=env)

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

    def test_staged_rename_counts_the_old_path(self):
        self.check("before")
        git(self.repo, "mv", "keep.txt", "a2.txt")
        result = self.check("after", allowed="a2.txt")
        self.assertEqual((result.returncode, result.stdout), (1, "Scope: outside allowed: keep.txt\n"),
                         result.stderr)

    def nested_repo(self, path):
        path.mkdir(parents=True)
        subprocess.run(["git", "init", "-q", str(path)], check=True)
        (path / "a.c").write_text("a\n", encoding="utf-8")
        git(path, "add", ".")
        git(path, "commit", "-q", "-m", "nested")

    def test_edits_inside_an_untracked_nested_repo_count(self):
        # git status lists a cloned repo (a colcon src/ checkout, say) only as `?? src/driver/`.
        driver = self.repo / "src/driver"
        self.nested_repo(driver)
        self.check("before")
        (driver / "a.c").write_text("changed\n", encoding="utf-8")
        (driver / "new.c").write_text("new\n", encoding="utf-8")
        result = self.check("after", allowed="src/driver/a.c")
        self.assertEqual(result.stdout, "Scope: outside allowed: src/driver/new.c\n", result.stderr)
        (driver / "new.c").unlink()
        (driver / "a.c").unlink()
        result = self.check("after", allowed="keep.txt")
        self.assertEqual(result.stdout, "Scope: outside allowed: src/driver/a.c\n", result.stderr)
        git(driver, "commit", "-q", "-am", "worker commit")  # clean again, but its HEAD moved
        result = self.check("after", allowed="keep.txt")
        self.assertEqual(result.stdout, "Scope: outside allowed: src/driver/\n", result.stderr)

    def test_edits_inside_an_already_dirty_submodule_count(self):
        lib = self.temp / "lib"
        self.nested_repo(lib)
        git(self.repo, "-c", "protocol.file.allow=always", "submodule", "add", "-q", lib.as_posix(), "sub")
        git(self.repo, "commit", "-q", "-m", "add submodule")
        (self.repo / "sub/a.c").write_text("dirty before\n", encoding="utf-8")
        self.check("before")
        (self.repo / "sub/a.c").write_text("edited again\n", encoding="utf-8")
        result = self.check("after", allowed="keep.txt")
        self.assertEqual(result.stdout, "Scope: outside allowed: sub/a.c\n", result.stderr)

    def test_ignored_files_count_but_the_orchestra_workspace_does_not(self):
        (self.repo / ".gitignore").write_text(".env\ndist/\n.orchestra/\n", encoding="utf-8")
        git(self.repo, "add", ".gitignore")
        git(self.repo, "commit", "-q", "-m", "ignore")
        self.check("before")
        (self.repo / ".env").write_text("secret\n", encoding="utf-8")
        (self.repo / "dist").mkdir()
        (self.repo / "dist/out.js").write_text("x\n", encoding="utf-8")
        (self.repo / ".orchestra").mkdir()
        (self.repo / ".orchestra/ledger.md").write_text("ledger\n", encoding="utf-8")
        result = self.check("after", allowed="keep.txt")
        self.assertEqual(result.stdout, "Scope: outside allowed: .env, dist/\n", result.stderr)

    @unittest.skipIf(os.name == "nt", "POSIX shell command")
    def test_nested_repo_config_cannot_run_a_command(self):
        # The check runs git on a repo the worker made; core.fsmonitor would execute.
        evil = self.repo / "evil"
        self.nested_repo(evil)
        marker = self.temp / "ran"
        with (evil / ".git/config").open("a", encoding="utf-8") as config:
            config.write(f"[core]\n\tfsmonitor = touch {marker}; echo\n")
        self.check("before")
        self.check("after", allowed="keep.txt")
        self.assertFalse(marker.exists())

    def test_repository_holding_the_home_directory_is_unchecked(self):
        # A repository at $HOME lists every app cache as untracked: noise only.
        (self.repo / "user").mkdir()  # a real home exists, so realpath can resolve it
        for home in (self.repo, self.repo / "user"):
            result = self.check("before", home=home)
            self.assertEqual(result.returncode, 1, result.stderr)
            self.assertIn("holds the home directory", result.stdout)

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
