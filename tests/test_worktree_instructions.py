#!/usr/bin/env python3
"""Run with python3 tests/test_worktree_instructions.py [path/to/git-worktree-fallback.md]."""
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

# Search PATH like a shell: on Windows a bare "bash" can resolve to WSL's
# System32\bash.exe before Git Bash.
BASH = shutil.which("bash") or "bash"

SKILL = (Path(sys.argv.pop(1)) if len(sys.argv) > 1 else
         Path(__file__).resolve().parents[1] / "skills/using-git-worktrees/modules/git-worktree-fallback.md").resolve()


class WorktreeInstructionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        blocks = [body for _, body in re.findall(
            r"^([ \t]*)```bash\n(.*?)^\1```[ \t]*$", SKILL.read_text(encoding="utf-8"), re.S | re.M)]
        cls.selection = next(body for body in blocks if "LOCATION=.worktrees" in body)
        cls.safety = next(body for body in blocks if "repo_root=" in body and "check-ignore" in body)
        cls.creation = next(body for body in blocks if " worktree add " in body)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="worktree-instructions-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.subdir = self.root / "src"
        self.subdir.mkdir()
        (self.root / "worktrees").mkdir()
        (self.root / ".gitignore").write_text("worktrees/\n", encoding="utf-8")
        subprocess.run(["git", "init", "-q", str(self.root)], check=True, capture_output=True)

    def run_flow(self, cwd, create=False):
        script = "set -eu\n" + self.selection + "\n" + self.safety
        if create:
            script += "\n" + self.creation
        script += '\nprintf "SELECTED=%s\\n" "$selected"'
        return subprocess.run([BASH, "-c", script], cwd=cwd, capture_output=True, text=True, encoding="utf-8",
                              env={**os.environ, "BRANCH_NAME": "codex/test-worktree"})

    def assert_selected(self, result, expected):
        # The skill prints bash's physical spelling (/c/... in Git Bash,
        # /private/var/... on macOS), so compare against bash's own `pwd -P`.
        self.assertIn(f"SELECTED={self.bash_path(expected)}\n", result.stdout)

    def bash_path(self, path):
        return subprocess.run([BASH, "-c", 'cd -- "$1" && pwd -P', "_", str(path)], check=True,
                              capture_output=True, text=True, encoding="utf-8").stdout.strip()

    def test_existing_directory_selected_from_any_cwd(self):
        for cwd in (self.root, self.subdir):
            with self.subTest(cwd=cwd.name):
                result = self.run_flow(cwd)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assert_selected(result, self.root / "worktrees")

    def test_preferred_directory_requires_its_own_ignore_rule(self):
        (self.root / ".worktrees").mkdir()
        result = self.run_flow(self.subdir)
        self.assertEqual(result.returncode, 1, result.stderr)
        (self.root / ".gitignore").write_text("worktrees/\n.worktrees/\n", encoding="utf-8")
        result = self.run_flow(self.subdir)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assert_selected(result, self.root / ".worktrees")

    @unittest.skipUnless(os.name == "nt", "Windows drive paths")
    def test_windows_drive_location_is_absolute(self):
        external = Path(tempfile.mkdtemp(prefix="wt-external-"))
        self.addCleanup(shutil.rmtree, external, True)
        location = str(external).replace("\\", "/")
        script = f'set -eu\nLOCATION="{location}"\n' + self.safety + '\nprintf "SELECTED=%s\\n" "$selected"'
        result = subprocess.run([BASH, "-c", script], cwd=self.root, capture_output=True, text=True,
                                encoding="utf-8")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assert_selected(result, external)

    def commit_baseline(self):
        subprocess.run(["git", "-C", str(self.root), "-c", "user.name=Fixture",
                        "-c", "user.email=fixture@example.invalid", "-c", "commit.gpgsign=false",
                        "-c", "core.hooksPath=/dev/null", "commit", "-q", "--allow-empty",
                        "-m", "fixture baseline"], check=True, capture_output=True)

    def test_failed_creation_never_marks_an_existing_worktree(self):
        # The agent runs each block on its own, without `set -e`.
        self.commit_baseline()
        user = self.root / "worktrees/codex/test-worktree"
        subprocess.run(["git", "-C", str(self.root), "worktree", "add", "-q", "-b", "user", str(user)],
                       check=True, capture_output=True)
        script = "set -eu\n" + self.selection + "\n" + self.safety + "\nset +e\n" + self.creation
        result = subprocess.run([BASH, "-c", script], cwd=self.root, capture_output=True, text=True,
                                encoding="utf-8", env={**os.environ, "BRANCH_NAME": "codex/test-worktree"})
        self.assertNotEqual(result.returncode, 0, result.stdout)
        git_dir = subprocess.run(["git", "-C", str(user), "rev-parse", "--git-dir"],
                                 check=True, capture_output=True, text=True, encoding="utf-8").stdout.strip()
        self.assertFalse((Path(git_dir) / "orchestra-owned-worktree").exists())

    def test_creation_uses_selected_root_from_subdirectory(self):
        self.commit_baseline()
        result = self.run_flow(self.subdir, create=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        expected = self.root / "worktrees/codex/test-worktree"
        self.assertTrue((expected / ".git").is_file())
        self.assertFalse((self.root / ".worktrees").exists())
        actual = subprocess.run(["git", "-C", str(expected), "rev-parse", "--show-toplevel"],
                                check=True, capture_output=True, text=True, encoding="utf-8")
        self.assertTrue(os.path.samefile(actual.stdout.strip(), expected))
        git_dir = subprocess.run(["git", "-C", str(expected), "rev-parse", "--git-dir"],
                                 check=True, capture_output=True, text=True, encoding="utf-8").stdout.strip()
        self.assertEqual((Path(git_dir) / "orchestra-owned-worktree").read_text(encoding="utf-8").strip(),
                         self.bash_path(expected))


if __name__ == "__main__":
    unittest.main(verbosity=2)
