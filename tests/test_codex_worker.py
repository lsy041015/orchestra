#!/usr/bin/env python3
from pathlib import Path
import json
import os
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
WORKER = ROOT / "skills/orchestrator/scripts/codex-worker.mjs"
FAKE = ROOT / "tests/fake_codex.mjs"
PROMPT = "Implement the requested change.\n"


class CodexWorkerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="codex-worker-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "repo with spaces"
        self.root.mkdir()
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        (self.root / ".gitignore").write_text("argv.json\nstdin.txt\n", encoding="utf-8")
        (self.root / "baseline.txt").write_text("baseline\n", encoding="utf-8")
        self.brief = self.root / "brief with spaces.md"
        self.brief.write_text(PROMPT, encoding="utf-8")
        subprocess.run(["git", "-C", str(self.root), "add", "."], check=True)
        subprocess.run(["git", "-C", str(self.root), "-c", "user.name=Fixture",
                        "-c", "user.email=fixture@example.invalid", "commit", "-q",
                        "-m", "baseline"], check=True)

    def run_worker(self, *extra, mode="ok", cwd=None, brief=None, model="gpt-6-luna"):
        cwd = Path(cwd or self.root)
        brief = Path(brief or self.brief)
        env = os.environ.copy()
        env.update(ORCHESTRA_CODEX_BIN=str(FAKE), FAKE_MODE=mode)
        return subprocess.run([
            "node", str(WORKER), "--model", model, "--effort", "high",
            "--cwd", str(cwd), "--brief", str(brief), "--allowed", "a.txt", *extra,
        ], cwd=ROOT, env=env, capture_output=True, text=True)

    def test_success_prints_message_thread_scope(self):
        result = self.run_worker()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout,
                         "Status: DONE\nChanged files: a.txt\n"
                         "Codex thread: t-123\nScope: ok\n")
        self.assertEqual((self.root / "stdin.txt").read_text(encoding="utf-8"), PROMPT)
        args = json.loads((self.root / "argv.json").read_text(encoding="utf-8"))
        for item in ("exec", "--json", "-s", "workspace-write",
                     "model_reasoning_effort=high"):
            self.assertIn(item, args)

    def test_scope_flags_outside_file(self):
        result = self.run_worker(mode="touch")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Scope: outside allowed: b.txt", result.stdout)

    def test_preexisting_dirty_file_unchanged_is_not_flagged(self):
        (self.root / "c.txt").write_text("preexisting\n", encoding="utf-8")
        result = self.run_worker(mode="touch")
        self.assertEqual(result.returncode, 0, result.stderr)
        scope = next(line for line in result.stdout.splitlines() if line.startswith("Scope:"))
        self.assertEqual(scope, "Scope: outside allowed: b.txt")

    def test_resume_uses_thread_id(self):
        result = self.run_worker("--resume", "t-123")
        self.assertEqual(result.returncode, 0, result.stderr)
        args = json.loads((self.root / "argv.json").read_text(encoding="utf-8"))
        self.assertEqual(args[:3], ["exec", "resume", "t-123"])
        self.assertIn("sandbox_mode=workspace-write", args)
        self.assertNotIn("-s", args)

    def test_codex_failure_reports_blocked(self):
        result = self.run_worker(mode="fail")
        self.assertEqual(result.returncode, 1)
        self.assertIn("Status: BLOCKED", result.stdout)
        self.assertIn("Unresolved: boom", result.stdout)
        result = self.run_worker(mode="event-fail")
        self.assertEqual(result.returncode, 1)
        self.assertIn("Status: BLOCKED", result.stdout)
        self.assertIn("Unresolved: Codex reported a failure", result.stdout)
        self.assertNotIn("Status: DONE", result.stdout)

    def test_rejects_bad_model(self):
        for model in ("x; rm", "gpt-model\n"):
            with self.subTest(model=repr(model)):
                result = self.run_worker(model=model)
                self.assertEqual(result.returncode, 2)
                self.assertFalse((self.root / "argv.json").exists())

    def test_rejects_bad_resume(self):
        result = self.run_worker("--resume", "t-123\n")
        self.assertEqual(result.returncode, 2)
        self.assertFalse((self.root / "argv.json").exists())

    def test_non_git_dir_scope_unchecked(self):
        with tempfile.TemporaryDirectory(prefix="codex-worker-plain-") as temp:
            cwd = Path(temp)
            brief = cwd / "brief.md"
            brief.write_text(PROMPT, encoding="utf-8")
            result = self.run_worker(mode="ok", cwd=cwd, brief=brief)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Scope: unchecked (not a git repo)", result.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=2)
