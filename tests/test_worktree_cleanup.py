#!/usr/bin/env python3
"""Orchestra removes only worktrees it created."""
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

# Search PATH like a shell: on Windows a bare "bash" can resolve to WSL's
# System32\bash.exe before Git Bash.
BASH = shutil.which("bash") or "bash"


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills/finishing-a-development-branch/SKILL.md"


def git(repo, *args):
    return subprocess.run(["git", "-C", str(repo), "-c", "user.name=Fixture",
                           "-c", "user.email=fixture@example.invalid", *args],
                          check=True, capture_output=True, text=True, encoding="utf-8")


class WorktreeCleanupTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.blocks = [body for _, body in re.findall(
            r"^([ \t]*)```bash\n(.*?)^\1```[ \t]*$",
            SKILL.read_text(encoding="utf-8"), re.S | re.M)]

    def temp_dir(self, prefix):
        temp = tempfile.TemporaryDirectory(prefix=prefix)
        self.addCleanup(temp.cleanup)
        return Path(temp.name)

    def run_block(self, needle, cwd, **placeholders):
        # One block exactly as the agent runs it: a fresh shell, no `set -e`.
        script = next(body for body in self.blocks if needle in body)
        for key, value in placeholders.items():
            script = script.replace(key, value)
        return subprocess.run([BASH, "-c", script], cwd=cwd, capture_output=True, text=True,
                              encoding="utf-8")

    def merge_block(self, cwd):
        return self.run_block("git merge <feature-branch>", cwd, **{
            "<base-branch>": "main", "<feature-branch>": "feat", "<test command>": "true"})

    def repo_with_feature(self, temp):
        repo = temp / "repo"
        repo.mkdir()
        subprocess.run(["git", "init", "-q", str(repo)], check=True)
        git(repo, "symbolic-ref", "HEAD", "refs/heads/main")
        git(repo, "commit", "-q", "--allow-empty", "-m", "baseline")
        git(repo, "checkout", "-q", "-b", "feat")
        git(repo, "commit", "-q", "--allow-empty", "-m", "feature work")
        git(repo, "checkout", "-q", "main")
        return repo

    def test_merge_stops_when_base_checkout_fails(self):
        temp = self.temp_dir("finish-merge-")
        repo = self.repo_with_feature(temp)
        git(repo, "checkout", "-q", "-b", "wip", "main")
        git(repo, "worktree", "add", "-q", str(temp / "other"), "main")  # `checkout main` now fails
        self.merge_block(repo)
        merged = subprocess.run(["git", "-C", str(repo), "merge-base", "--is-ancestor", "feat", "wip"])
        self.assertNotEqual(merged.returncode, 0, "feature was merged into the wrong branch")

    def test_merge_without_upstream_reaches_base(self):
        repo = self.repo_with_feature(self.temp_dir("finish-merge-"))
        git(repo, "checkout", "-q", "feat")
        self.merge_block(repo)
        merged = subprocess.run(["git", "-C", str(repo), "merge-base", "--is-ancestor", "feat", "main"])
        self.assertEqual(merged.returncode, 0)

    def test_failed_merge_fails_the_block_without_running_tests(self):
        # Tests on the unmerged base would pass and hide the failed merge.
        repo = self.repo_with_feature(self.temp_dir("finish-merge-"))
        for branch in ("feat", "main"):
            git(repo, "checkout", "-q", branch)
            (repo / "f.txt").write_text(branch, encoding="utf-8")
            git(repo, "add", "f.txt")
            git(repo, "commit", "-q", "-m", branch)
        result = self.run_block("git merge <feature-branch>", repo, **{
            "<base-branch>": "main", "<feature-branch>": "feat", "<test command>": "touch tests-ran"})
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertFalse((repo / "tests-ran").exists())

    def test_merge_from_bare_repository_worktree_does_not_merge_in_place(self):
        # A bare repository has no main worktree to change into.
        temp = self.temp_dir("finish-bare-")
        repo = self.repo_with_feature(temp)
        bare = temp / "repo.git"
        subprocess.run(["git", "clone", "-q", "--bare", str(repo), str(bare)], check=True)
        feature = temp / "feat-wt"
        git(bare, "worktree", "add", "-q", str(feature), "feat")
        self.merge_block(feature)
        branch = git(feature, "branch", "--show-current").stdout.strip()
        self.assertEqual(branch, "feat")

    def owned_worktree(self, owned, ignored_file=False):
        temp = self.temp_dir("worktree-cleanup-")
        repo = temp / "repo"
        repo.mkdir()
        subprocess.run(["git", "init", "-q", str(repo)], check=True)
        (repo / ".gitignore").write_text(".env\n", encoding="utf-8")
        git(repo, "add", ".gitignore")
        git(repo, "commit", "-q", "-m", "baseline")
        worktree = repo / ".worktrees/user"
        git(repo, "worktree", "add", "-q", "-b", "user", str(worktree))
        if ignored_file:
            (worktree / ".env").write_text("SECRET=1\n", encoding="utf-8")
        if owned:
            git_dir = git(worktree, "rev-parse", "--absolute-git-dir").stdout.strip()
            # Same command the creation step uses, so the marker matches
            # bash's own path spelling (/c/... under Git Bash).
            subprocess.run([BASH, "-c", 'cd -- "$1" && pwd -P > "$2"', "_",
                            str(worktree), str(Path(git_dir) / "orchestra-owned-worktree")],
                           check=True)
        return repo, worktree

    def cleanup_block(self, repo, worktree):
        return self.run_block('git worktree remove "$WORKTREE_PATH"', repo,
                              **{"<worktree path from Step 2>": str(worktree)})

    def test_cleanup_requires_ownership_marker(self):
        for owned in (False, True):
            with self.subTest(owned=owned):
                repo, worktree = self.owned_worktree(owned)
                result = self.cleanup_block(repo, worktree)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual((worktree / ".git").exists(), not owned)

    def test_cleanup_keeps_worktree_with_ignored_files(self):
        # `git worktree remove` would delete the ignored .env without a word.
        repo, worktree = self.owned_worktree(owned=True, ignored_file=True)
        result = self.cleanup_block(repo, worktree)
        self.assertTrue((worktree / ".env").exists())
        self.assertIn(".env", result.stdout)

    def test_cleanup_moves_orchestra_records_to_main_checkout(self):
        # The self-ignored ledger would otherwise block cleanup or vanish with the worktree.
        repo, worktree = self.owned_worktree(owned=True)
        plan = worktree / ".orchestra/sdd/plan"
        plan.mkdir(parents=True)
        (worktree / ".orchestra/sdd/.gitignore").write_text("*\n", encoding="utf-8")
        (plan / "progress.md").write_text("Task 1: complete\n", encoding="utf-8")
        result = self.cleanup_block(repo, worktree)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(worktree.exists(), result.stdout)
        kept = list((repo / ".orchestra/archive").glob("*/sdd/plan/progress.md"))
        self.assertEqual([p.read_text(encoding="utf-8") for p in kept], ["Task 1: complete\n"])
        self.assertEqual(git(repo, "status", "--porcelain").stdout, "")


if __name__ == "__main__":
    unittest.main(verbosity=2)
