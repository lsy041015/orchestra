#!/usr/bin/env python3
"""Regression tests for SDD workspace safety and task completion."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

# Search PATH like a shell: on Windows a bare "bash" can resolve to WSL's
# System32\bash.exe before Git Bash.
BASH = shutil.which("bash") or "bash"


ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = ROOT / "skills/subagent-driven-development/scripts/sdd-workspace"
TASK_DONE = ROOT / "skills/executing-plans/scripts/task-done"


class SddSafetyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="sdd-safety-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "repo"
        self.root.mkdir()
        self.plan = self.root / "plan.md"
        self.plan.write_text("# Plan\n", encoding="utf-8")
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)

    def run_script(self, script, *args):
        return subprocess.run([BASH, str(script), *map(str, args)], cwd=self.root,
                              capture_output=True, text=True, encoding="utf-8")

    def test_workspace_rejects_symlink_outside_repo(self):
        outside = Path(self.temp.name) / "outside"
        outside.mkdir()
        try:
            (self.root / ".orchestra").symlink_to(outside, target_is_directory=True)
        except OSError as error:  # Windows without Developer Mode
            self.skipTest(f"cannot create symlinks: {error}")
        result = self.run_script(WORKSPACE, self.plan)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(list(outside.iterdir()), [])

    def test_workspace_preserves_existing_ignore_file(self):
        base = self.root / ".orchestra/sdd"
        base.mkdir(parents=True)
        (base / ".gitignore").write_text("# keep me", encoding="utf-8")
        result = self.run_script(WORKSPACE, self.plan)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((base / ".gitignore").read_text(encoding="utf-8"), "# keep me\n*\n")

    def test_workspace_marker_is_repo_relative_from_any_cwd(self):
        # Git Bash spells the root C:/... in rev-parse but /c/... in pwd -P;
        # both sides must use one spelling or the marker turns absolute.
        (self.root / "docs").mkdir()
        plan = self.root / "docs/plan.md"
        plan.write_text("# Plan\n", encoding="utf-8")
        first = self.run_script(WORKSPACE, plan)
        self.assertEqual(first.returncode, 0, first.stderr)
        marker = self.root / ".orchestra/sdd/plan/plan-path"
        self.assertEqual(marker.read_text(encoding="utf-8"), "docs/plan.md\n")
        again = subprocess.run([BASH, str(WORKSPACE), "plan.md"], cwd=self.root / "docs",
                               capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(again.returncode, 0, again.stderr)
        self.assertEqual(again.stdout, first.stdout)
        # A workspace whose marker holds the absolute spelling still belongs to the plan.
        plan_abs = subprocess.run([BASH, "-c", 'cd -- "$1" && printf "%s/plan.md\\n" "$(pwd -P)"', "_",
                                   str(self.root / "docs")], check=True, capture_output=True,
                                  text=True, encoding="utf-8").stdout
        marker.write_text(plan_abs, encoding="utf-8")
        legacy = self.run_script(WORKSPACE, plan)
        self.assertEqual(legacy.stdout, first.stdout, legacy.stderr)

    def test_task_done_rejects_a_forged_task_number(self):
        subprocess.run(["git", "-C", str(self.root), "-c", "user.name=Fixture",
                        "-c", "user.email=fixture@example.invalid", "commit",
                        "-q", "--allow-empty", "-m", "baseline"], check=True)
        sha = subprocess.run(["git", "-C", str(self.root), "rev-parse", "HEAD"],
                             check=True, capture_output=True, text=True, encoding="utf-8").stdout.strip()
        result = self.run_script(TASK_DONE, self.plan, "7\nTask 2: complete (forged)", sha, "--", "true")
        self.assertEqual(result.returncode, 2)
        ledger = self.root / ".orchestra/sdd/plan/progress.md"
        self.assertFalse(ledger.exists() and "forged" in ledger.read_text(encoding="utf-8"))

    def test_task_done_records_successful_silent_command(self):
        subprocess.run(["git", "-C", str(self.root), "-c", "user.name=Fixture",
                        "-c", "user.email=fixture@example.invalid", "commit",
                        "-q", "--allow-empty", "-m", "baseline"], check=True)
        sha = subprocess.run(["git", "-C", str(self.root), "rev-parse", "HEAD"],
                             check=True, capture_output=True, text=True, encoding="utf-8").stdout.strip()
        result = self.run_script(TASK_DONE, self.plan, 1, sha, "--", "true")
        self.assertEqual(result.returncode, 0, result.stderr)
        ledger = self.root / ".orchestra/sdd/plan/progress.md"
        self.assertIn("Task 1: complete", ledger.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
