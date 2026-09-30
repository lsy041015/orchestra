#!/usr/bin/env python3
"""task-start writes the task's brief into the plan's workspace and prints BASE."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

# Search PATH like a shell: on Windows a bare "bash" can resolve to WSL's
# System32\bash.exe before Git Bash.
BASH = shutil.which("bash") or "bash"

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills/executing-plans/scripts/task-start"
WORKSPACE = ROOT / "skills/subagent-driven-development/scripts/sdd-workspace"
PLAN = "# Plan\n\n### Task 1: first\n\nDo A.\n\n### Task 2: second\n\nDo B.\n"


class TaskStartTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix="task-start-")
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name) / "repo"
        self.root.mkdir()
        (self.root / "plan.md").write_text(PLAN, encoding="utf-8")
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        subprocess.run(["git", "-C", str(self.root), "-c", "user.name=Fixture",
                        "-c", "user.email=fixture@example.invalid", "commit", "-q",
                        "--allow-empty", "-m", "baseline"], check=True)

    def run_bash(self, script, *args):
        return subprocess.run([BASH, str(script), *args], cwd=self.root,
                              capture_output=True, text=True, encoding="utf-8")

    def test_prints_brief_path_and_head(self):
        result = self.run_bash(SCRIPT, "plan.md", "2")
        self.assertEqual(result.returncode, 0, result.stderr)
        # The workspace path in bash's own spelling (/c/... under Git Bash).
        workspace = self.run_bash(WORKSPACE, "plan.md").stdout.strip()
        head = subprocess.run(["git", "-C", str(self.root), "rev-parse", "HEAD"], check=True,
                              capture_output=True, text=True, encoding="utf-8").stdout.strip()
        self.assertEqual(result.stdout, f"brief: {workspace}/task-2-brief.md\nbase: {head}\n")
        brief = (self.root / ".orchestra/sdd/plan/task-2-brief.md").read_text(encoding="utf-8")
        self.assertEqual(brief, "### Task 2: second\n\nDo B.\n")

    def test_missing_task_prints_nothing_and_fails(self):
        result = self.run_bash(SCRIPT, "plan.md", "3")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")
        self.assertIn("task 3 not found", result.stderr)


if __name__ == "__main__":
    unittest.main(verbosity=2)
