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
        self.assertEqual(result.stdout, "Scope: outside allowed: src/driver/, src/driver/a.c\n", result.stderr)

    def test_edits_inside_an_already_dirty_submodule_count(self):
        self.add_submodule()
        (self.repo / "sub/a.c").write_text("dirty before\n", encoding="utf-8")
        self.check("before")
        (self.repo / "sub/a.c").write_text("edited again\n", encoding="utf-8")
        result = self.check("after", allowed="keep.txt")
        self.assertEqual(result.stdout, "Scope: outside allowed: sub/a.c\n", result.stderr)

    def add_submodule(self):
        lib = self.temp / "lib"
        self.nested_repo(lib)
        git(self.repo, "-c", "protocol.file.allow=always", "submodule", "add", "-q", lib.as_posix(), "sub")
        git(self.repo, "commit", "-q", "-m", "add submodule")
        return self.repo / "sub"

    def test_one_edit_in_a_clean_submodule_flags_only_that_file(self):
        sub = self.add_submodule()
        (sub / "b.c").write_text("b\n", encoding="utf-8")
        git(sub, "add", "b.c")
        git(sub, "commit", "-q", "-m", "second file")
        git(self.repo, "commit", "-q", "-am", "bump submodule")
        self.check("before")
        (sub / "a.c").write_text("edited\n", encoding="utf-8")
        result = self.check("after", allowed="keep.txt")
        self.assertEqual(result.stdout, "Scope: outside allowed: sub/a.c\n", result.stderr)

    def test_submodule_ignore_settings_do_not_hide_edits_or_commits(self):
        sub = self.add_submodule()
        git(self.repo, "config", "-f", ".gitmodules", "submodule.sub.ignore", "all")
        git(self.repo, "commit", "-q", "-am", "ignore the submodule")
        git(self.repo, "config", "diff.ignoreSubmodules", "all")
        self.check("before")
        (sub / "a.c").write_text("edited\n", encoding="utf-8")
        git(sub, "commit", "-q", "-am", "worker commit")
        result = self.check("after", allowed="keep.txt")
        self.assertEqual(result.stdout, "Scope: outside allowed: sub, sub/a.c\n", result.stderr)
        # A whole-directory entry covers the submodule's own entry too.
        result = self.check("after", allowed="sub/")
        self.assertEqual((result.returncode, result.stdout), (0, "Scope: ok\n"), result.stderr)

    def test_repointing_a_submodule_git_file_counts(self):
        sub = self.add_submodule()
        self.check("before")
        (sub / ".git").write_text("gitdir: ../elsewhere\n", encoding="utf-8")
        result = self.check("after", allowed="keep.txt")
        self.assertIn("sub/.git", result.stdout, result.stderr)

    @unittest.skipIf(os.name == "nt", "POSIX shell command")
    def test_submodule_filter_driver_cannot_run_a_command(self):
        # Without --ignore-submodules, the top-level status ran this driver too.
        sub = self.add_submodule()
        marker = self.temp / "ran"
        (sub / ".gitattributes").write_text("* filter=evil\n", encoding="utf-8")
        git(sub, "add", ".gitattributes")
        git(sub, "commit", "-q", "-m", "attributes")
        git(self.repo, "commit", "-q", "-am", "bump submodule")
        git(sub, "config", "filter.evil.clean", f"touch {marker}; cat")
        self.check("before")
        os.utime(sub / "a.c", (1, 1))  # same size, new mtime: content would be compared
        result = self.check("after", allowed="keep.txt")
        self.assertFalse(marker.exists())
        self.assertEqual(result.stdout, "Scope: outside allowed: sub/a.c\n", result.stderr)

    def test_index_flags_do_not_hide_edits(self):
        (self.repo / "skip.txt").write_text("skip\n", encoding="utf-8")
        git(self.repo, "add", "skip.txt")
        git(self.repo, "commit", "-q", "-m", "second file")
        git(self.repo, "update-index", "--assume-unchanged", "keep.txt")
        git(self.repo, "update-index", "--skip-worktree", "skip.txt")
        self.check("before")
        (self.repo / "keep.txt").write_text("hidden edit\n", encoding="utf-8")
        (self.repo / "skip.txt").write_text("hidden edit\n", encoding="utf-8")
        result = self.check("after", allowed="a.txt")
        self.assertEqual(result.stdout, "Scope: outside allowed: keep.txt, skip.txt\n", result.stderr)

    def test_rewrite_directly_inside_an_ignored_directory_counts(self):
        (self.repo / ".gitignore").write_text("dist/\n", encoding="utf-8")
        git(self.repo, "add", ".gitignore")
        git(self.repo, "commit", "-q", "-m", "ignore")
        (self.repo / "dist").mkdir()
        (self.repo / "dist/app.js").write_text("x\n", encoding="utf-8")
        self.check("before")
        result = self.check("after", allowed="keep.txt")
        self.assertEqual(result.stdout, "Scope: ok\n", result.stderr)
        with (self.repo / "dist/app.js").open("a", encoding="utf-8") as app:
            app.write("injected\n")
        result = self.check("after", allowed="keep.txt")
        self.assertEqual(result.stdout, "Scope: outside allowed: dist/ (ignored)\n", result.stderr)

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
        self.assertEqual(result.stdout, "Scope: outside allowed: .env (ignored), dist/ (ignored)\n",
                         result.stderr)

    def test_ignored_files_inside_a_nested_repo_are_labelled(self):
        driver = self.repo / "src/driver"
        self.nested_repo(driver)
        (driver / ".gitignore").write_text("build/\n", encoding="utf-8")
        self.check("before")
        (driver / "build").mkdir()
        (driver / "build/out.o").write_text("o\n", encoding="utf-8")
        result = self.check("after", allowed="keep.txt")
        self.assertEqual(result.stdout,
                         "Scope: outside allowed: src/driver/build/ (ignored)\n",
                         result.stderr)

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

    @unittest.skipIf(os.name == "nt", "POSIX shell command")
    def test_nested_repo_filter_driver_cannot_run_a_command(self):
        # git status re-reads a file whose mtime moved through its clean filter.
        evil = self.repo / "evil"
        self.nested_repo(evil)
        marker = self.temp / "ran"
        (evil / ".gitattributes").write_text("* filter=evil\n", encoding="utf-8")
        git(evil, "add", ".gitattributes")
        git(evil, "commit", "-q", "-m", "attributes")
        with (evil / ".git/config").open("a", encoding="utf-8") as config:
            config.write(f'[filter "evil"]\n\tclean = "touch {marker}; cat"\n\tprocess = "touch {marker}"\n')
        self.check("before")
        os.utime(evil / "a.c", (1, 1))  # same size, new mtime: content would be compared
        result = self.check("after", allowed="keep.txt")
        self.assertFalse(marker.exists())
        self.assertEqual(result.stdout, "Scope: outside allowed: evil/a.c\n", result.stderr)

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
