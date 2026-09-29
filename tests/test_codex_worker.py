#!/usr/bin/env python3
from pathlib import Path
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from unittest import mock


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

    def run_worker(self, *extra, mode="ok", cwd=None, brief=None, model="gpt-6-luna",
                   effort="high", allowed="a.txt"):
        cwd = Path(cwd or self.root)
        brief = Path(brief or self.brief)
        env = os.environ.copy()
        env.update(ORCHESTRA_CODEX_BIN=str(FAKE), FAKE_MODE=mode)
        return subprocess.run([
            "node", str(WORKER), "--model", model, "--effort", effort,
            "--cwd", str(cwd), "--brief", str(brief), "--allowed", allowed, *extra,
        ], cwd=ROOT, env=env, capture_output=True, text=True, encoding="utf-8")

    def scope(self, result):
        return next(line for line in result.stdout.splitlines() if line.startswith("Scope:"))

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
        self.assertEqual(self.scope(result), "Scope: outside allowed: b.txt")

    def test_subdirectory_cwd_scope_is_relative_to_cwd(self):
        sub = self.root / "pkg"
        sub.mkdir()
        (sub / "b.txt").write_text("dirty before the run\n", encoding="utf-8")
        brief = sub / "brief.md"
        brief.write_text(PROMPT, encoding="utf-8")
        result = self.run_worker(mode="touch", cwd=sub, brief=brief)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.scope(result), "Scope: outside allowed: pkg/b.txt")

    def test_brief_outside_cwd_is_rejected(self):
        # The Codex sandbox writes only inside --cwd, so the report that lives
        # next to the brief would be unwritable.
        sub = self.root / "pkg"
        sub.mkdir()
        result = self.run_worker(cwd=sub)
        self.assertEqual(result.returncode, 2)
        self.assertIn("--brief", result.stderr)
        self.assertFalse((sub / "argv.json").exists())

    def test_allowed_directory_entry_covers_new_files(self):
        result = self.run_worker(mode="nested", allowed="a.txt,ou/")
        self.assertEqual(self.scope(result), "Scope: outside allowed: out/deep/c.txt")
        shutil.rmtree(self.root / "out")
        result = self.run_worker(mode="nested", allowed="a.txt, out/")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.scope(result), "Scope: ok")

    def test_accepts_every_codex_effort(self):
        for effort in ("none", "minimal", "low", "medium", "high", "xhigh", "max", "ultra"):
            with self.subTest(effort=effort):
                result = self.run_worker(effort=effort)
                self.assertEqual(result.returncode, 0, result.stderr)
                args = json.loads((self.root / "argv.json").read_text(encoding="utf-8"))
                self.assertIn(f"model_reasoning_effort={effort}", args)

    def test_resume_uses_thread_id(self):
        result = self.run_worker("--resume", "t-123")
        self.assertEqual(result.returncode, 0, result.stderr)
        args = json.loads((self.root / "argv.json").read_text(encoding="utf-8"))
        self.assertEqual(args[:3], ["exec", "resume", "t-123"])
        self.assertIn("sandbox_mode=workspace-write", args)
        self.assertNotIn("-s", args)

    def test_network_is_opt_in(self):
        flag = "sandbox_workspace_write.network_access=true"
        for value, expected in (("0", False), ("1", True)):
            with self.subTest(value=value), mock.patch.dict(os.environ, {"ORCHESTRA_CODEX_NETWORK": value}):
                result = self.run_worker()
                self.assertEqual(result.returncode, 0, result.stderr)
                args = json.loads((self.root / "argv.json").read_text(encoding="utf-8"))
                self.assertEqual(flag in args, expected)

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

    def test_recovered_stream_error_is_not_a_failure(self):
        result = self.run_worker(mode="retry-error")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(result.stdout.startswith("Status: DONE\n"), result.stdout)

    def test_reply_without_status_block_is_blocked(self):
        result = self.run_worker(mode="no-status")
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout.splitlines()[:2], [
            "Status: BLOCKED",
            "Unresolved: Codex reply has no status block: Which file should I change?",
        ])

    def test_git_failure_after_run_is_not_reported_ok(self):
        result = self.run_worker(mode="break-git")
        self.assertTrue(self.scope(result).startswith("Scope: unchecked (git status failed after the run: "),
                        result.stdout)

    def test_api_error_json_is_reduced_to_its_message(self):
        result = self.run_worker(mode="api-error")
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout.splitlines()[:2], [
            "Status: BLOCKED",
            "Unresolved: Unsupported value: 'minimal' is not supported with the 'gpt-6-luna' model.",
        ])

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
        self.assertTrue(self.scope(result).startswith("Scope: unchecked (git: "), result.stdout)

    @unittest.skipUnless(os.name == "nt", "Windows command lookup")
    def test_windows_ignores_codex_planted_in_cwd(self):
        # cmd.exe and CreateProcess search the current directory before PATH
        # unless NoDefaultCurrentDirectoryInExePath is set. Claude Code sets it;
        # a plain terminal does not.
        shim = Path(self.temp.name) / "bin"
        shim.mkdir()
        (shim / "codex.cmd").write_text(f'@node "{FAKE}" %*\r\n', encoding="utf-8")
        (self.root / "codex.cmd").write_text(
            '@echo {"type":"thread.started","thread_id":"planted"}\r\n', encoding="utf-8")
        env = {k: v for k, v in os.environ.items()
               if k.upper() not in ("NODEFAULTCURRENTDIRECTORYINEXEPATH", "ORCHESTRA_CODEX_BIN")}
        env["PATH"] = str(shim) + os.pathsep + env.get("PATH", "")
        result = subprocess.run([
            "node", str(WORKER), "--model", "gpt-6-luna", "--effort", "high", "--cwd", str(self.root),
            "--brief", str(self.brief), "--allowed", "a.txt",
        ], cwd=self.root, env=env, capture_output=True, text=True, encoding="utf-8")
        self.assertIn("Codex thread: t-123", result.stdout, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main(verbosity=2)
