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

    def merge_flow(self, base_elsewhere):
        # Option 1 exactly as the agent runs it: one block, no `set -e`.
        merge = next(body for body in self.blocks if "git merge <feature-branch>" in body)
        script = (merge.replace("<base-branch>", "main").replace("<feature-branch>", "feat")
                  .replace("<test command>", "true"))
        temp = tempfile.TemporaryDirectory(prefix="finish-merge-")
        self.addCleanup(temp.cleanup)
        repo = Path(temp.name) / "repo"
        repo.mkdir()
        subprocess.run(["git", "init", "-q", str(repo)], check=True)
        git(repo, "symbolic-ref", "HEAD", "refs/heads/main")
        git(repo, "commit", "-q", "--allow-empty", "-m", "baseline")
        git(repo, "checkout", "-q", "-b", "feat")
        git(repo, "commit", "-q", "--allow-empty", "-m", "feature work")
        git(repo, "checkout", "-q", "-b", "wip", "main")
        if base_elsewhere:  # makes `git checkout main` fail
            git(repo, "worktree", "add", "-q", str(Path(temp.name) / "other"), "main")
        subprocess.run([BASH, "-c", script], cwd=repo, capture_output=True, text=True, encoding="utf-8")
        return repo

    def test_merge_stops_when_base_checkout_fails(self):
        repo = self.merge_flow(base_elsewhere=True)
        merged = subprocess.run(["git", "-C", str(repo), "merge-base", "--is-ancestor", "feat", "wip"])
        self.assertNotEqual(merged.returncode, 0, "feature was merged into the wrong branch")

    def test_merge_without_upstream_reaches_base(self):
        repo = self.merge_flow(base_elsewhere=False)
        merged = subprocess.run(["git", "-C", str(repo), "merge-base", "--is-ancestor", "feat", "main"])
        self.assertEqual(merged.returncode, 0)

    def test_cleanup_requires_ownership_marker(self):
        cleanup = next(body for body in self.blocks if 'git worktree remove "$WORKTREE_PATH"' in body)
        for owned in (False, True):
            with self.subTest(owned=owned), tempfile.TemporaryDirectory(prefix="worktree-cleanup-") as temp:
                repo = Path(temp) / "repo"
                repo.mkdir()
                subprocess.run(["git", "init", "-q", str(repo)], check=True)
                subprocess.run(["git", "-C", str(repo), "-c", "user.name=Fixture",
                                "-c", "user.email=fixture@example.invalid", "commit",
                                "-q", "--allow-empty", "-m", "baseline"], check=True)
                worktree = repo / ".worktrees/user"
                subprocess.run(["git", "-C", str(repo), "worktree", "add", "-q", "-b",
                                "user", str(worktree)], check=True)
                git_dir = subprocess.run(["git", "-C", str(worktree), "rev-parse",
                                          "--git-dir"], check=True, capture_output=True,
                                         text=True, encoding="utf-8").stdout.strip()
                if owned:
                    # Same command the creation step uses, so the marker matches
                    # bash's own path spelling (/c/... under Git Bash).
                    subprocess.run([BASH, "-c", 'cd -- "$1" && pwd -P > "$2"', "_",
                                    str(worktree), str(Path(git_dir) / "orchestra-owned-worktree")],
                                   check=True)
                script = f'set -eu\nGIT_DIR="{git_dir}"\nWORKTREE_PATH="{worktree}"\n' + cleanup
                result = subprocess.run([BASH, "-c", script], cwd=repo,
                                        capture_output=True, text=True, encoding="utf-8")
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual((worktree / ".git").exists(), not owned)


if __name__ == "__main__":
    unittest.main(verbosity=2)
