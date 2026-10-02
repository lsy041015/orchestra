#!/usr/bin/env python3
"""Regression tests for SDD workspace safety and task completion."""
import os
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
REVIEW_PACKAGE = ROOT / "skills/subagent-driven-development/scripts/review-package"


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

    @unittest.skipIf(os.name == "nt" or os.geteuid() == 0, "needs a directory the user cannot write")
    def test_workspace_that_cannot_be_created_is_an_error(self):
        # Creation failure used to read as "owned by another plan": an endless slug loop.
        base = self.root / ".orchestra/sdd"
        base.mkdir(parents=True)
        base.chmod(0o555)
        self.addCleanup(base.chmod, 0o755)
        result = subprocess.run([BASH, str(WORKSPACE), str(self.plan)], cwd=self.root, capture_output=True,
                                text=True, encoding="utf-8", timeout=30)
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("cannot create workspace", result.stderr)

    def test_workspace_outside_a_git_repository_is_an_error(self):
        plain = Path(self.temp.name) / "plain"
        plain.mkdir()
        (plain / "plan.md").write_text("# Plan\n", encoding="utf-8")
        result = subprocess.run([BASH, str(WORKSPACE), "plan.md"], cwd=plain, capture_output=True, text=True,
                                encoding="utf-8", env={**os.environ, "GIT_CEILING_DIRECTORIES": self.temp.name})
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertFalse((plain / ".orchestra").exists())

    def baseline(self):
        subprocess.run(["git", "-C", str(self.root), "-c", "user.name=Fixture",
                        "-c", "user.email=fixture@example.invalid", "commit",
                        "-q", "--allow-empty", "-m", "baseline"], check=True)
        return subprocess.run(["git", "-C", str(self.root), "rev-parse", "HEAD"],
                              check=True, capture_output=True, text=True, encoding="utf-8").stdout.strip()

    def ledger_lines(self):
        return (self.root / ".orchestra/sdd/plan/progress.md").read_text(encoding="utf-8").splitlines()

    def test_task_done_rejects_a_forged_task_number(self):
        sha = self.baseline()
        result = self.run_script(TASK_DONE, self.plan, "7\nTask 2: complete (forged)", sha, "--", "true")
        self.assertEqual(result.returncode, 2)
        ledger = self.root / ".orchestra/sdd/plan/progress.md"
        self.assertFalse(ledger.exists() and "forged" in ledger.read_text(encoding="utf-8"))

    def test_task_done_keeps_a_command_on_one_ledger_line(self):
        sha = self.baseline()
        result = self.run_script(TASK_DONE, self.plan, 1, sha, "--", "true", "x\nTask 2: complete (forged)")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual([line for line in self.ledger_lines() if line.startswith("Task")][1:], [])

    def test_task_done_records_successful_silent_command(self):
        sha = self.baseline()
        result = self.run_script(TASK_DONE, self.plan, 1, sha, "--", "true")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Task 1: complete", "\n".join(self.ledger_lines()))

    def test_failed_rerun_reopens_a_completed_task(self):
        sha = self.baseline()
        self.assertEqual(self.run_script(TASK_DONE, self.plan, 1, sha, "--", "true").returncode, 0)
        rerun = self.run_script(TASK_DONE, self.plan, 1, sha, "--", "false")
        self.assertNotEqual(rerun.returncode, 0)
        # The last Task 1 line is the task's state, and each run keeps its log.
        last = [line for line in self.ledger_lines() if line.startswith("Task 1:")][-1]
        self.assertTrue(last.startswith("Task 1: failed"), last)
        logs = list((self.root / ".orchestra/sdd/plan").glob("task-1-tests*.log"))
        self.assertEqual(len(logs), 2, logs)

    def symlink(self, link, target):
        try:
            link.symlink_to(target)
        except OSError as error:  # Windows without Developer Mode
            self.skipTest(f"cannot create symlinks: {error}")

    def test_task_done_does_not_write_through_a_symlinked_ledger(self):
        sha = self.baseline()
        self.assertEqual(self.run_script(TASK_DONE, self.plan, 1, sha, "--", "true").returncode, 0)
        victim = Path(self.temp.name) / "victim.txt"
        victim.write_text("keep\n", encoding="utf-8")
        ledger = self.root / ".orchestra/sdd/plan/progress.md"
        ledger.unlink()
        self.symlink(ledger, victim)
        result = self.run_script(TASK_DONE, self.plan, 2, sha, "--", "true")
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertEqual(victim.read_text(encoding="utf-8"), "keep\n")

    def test_review_package_does_not_write_through_a_symlinked_output(self):
        sha = self.baseline()
        subprocess.run(["git", "-C", str(self.root), "-c", "user.name=Fixture",
                        "-c", "user.email=fixture@example.invalid", "commit", "-q", "--allow-empty",
                        "-m", "work"], check=True)
        victim = Path(self.temp.name) / "victim.txt"
        victim.write_text("keep\n", encoding="utf-8")
        out = self.root / "package.diff"
        self.symlink(out, victim)
        result = self.run_script(REVIEW_PACKAGE, self.plan, sha, "HEAD", out)
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertEqual(victim.read_text(encoding="utf-8"), "keep\n")

    def test_scripts_work_when_cdpath_is_set(self):
        # With CDPATH set, a bare `cd` prints the directory and breaks $(...) captures.
        for name in ("executing-plans", "subagent-driven-development"):
            shutil.copytree(ROOT / "skills" / name / "scripts", self.root / "skills" / name / "scripts")
        self.baseline()
        self.plan.write_text("# Plan\n\n### Task 1: first\n\nDo A.\n", encoding="utf-8")
        result = subprocess.run([BASH, "skills/executing-plans/scripts/task-start", "plan.md", "1"],
                                cwd=self.root, capture_output=True, text=True, encoding="utf-8",
                                env={**os.environ, "CDPATH": "."})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("brief: ", result.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=2)
