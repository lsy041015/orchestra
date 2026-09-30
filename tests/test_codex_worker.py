#!/usr/bin/env python3
from pathlib import Path
import json
import os
import shutil
import signal
import subprocess
import tempfile
import time
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
        # An empty Codex home: the worker must not read this machine's model cache.
        self.codex_home = Path(self.temp.name) / "codex-home"
        self.codex_home.mkdir()
        subprocess.run(["git", "-C", str(self.root), "add", "."], check=True)
        subprocess.run(["git", "-C", str(self.root), "-c", "user.name=Fixture",
                        "-c", "user.email=fixture@example.invalid", "commit", "-q",
                        "-m", "baseline"], check=True)

    def run_worker(self, *extra, mode="ok", cwd=None, brief=None, model="gpt-6-luna",
                   effort="high", allowed="a.txt"):
        cwd = Path(cwd or self.root)
        brief = Path(brief or self.brief)
        env = os.environ.copy()
        env.update(ORCHESTRA_CODEX_BIN=str(FAKE), FAKE_MODE=mode, CODEX_HOME=str(self.codex_home))
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
        self.assert_plugins_disabled(args)

    def assert_plugins_disabled(self, args):
        # The user's Codex plugins (another Superpowers, say) bring their own workflow.
        self.assertIn(["--disable", "plugins"], [args[i:i + 2] for i in range(len(args))])

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

    def test_linked_cwd_checks_the_real_repository(self):
        # git climbs from the link target: a link that lives in another
        # repository once made the check compare that checkout and print ok.
        outer = Path(self.temp.name) / "outer"
        outer.mkdir()
        subprocess.run(["git", "init", "-q", str(outer)], check=True)
        sub = self.root / "pkg"
        sub.mkdir()
        (sub / "brief.md").write_text(PROMPT, encoding="utf-8")
        link = outer / "link"
        try:
            link.symlink_to(sub, target_is_directory=True)
        except OSError:
            if os.name != "nt":
                raise
            import _winapi  # a junction needs no symlink privilege
            _winapi.CreateJunction(str(sub), str(link))
        result = self.run_worker(mode="touch", cwd=link, brief=link / "brief.md")
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

    def test_effort_missing_from_model_cache_is_blocked_before_codex_runs(self):
        # The API accepted gpt-6-luna + ultra although Codex lists only up to max.
        (self.codex_home / "models_cache.json").write_text(json.dumps({"models": [
            {"slug": "gpt-6-luna", "supported_reasoning_levels": [{"effort": "low"}, {"effort": "max"}]},
        ]}), encoding="utf-8")
        result = self.run_worker(effort="ultra")
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertTrue(result.stdout.startswith("Status: BLOCKED\n"), result.stdout)
        self.assertIn("low, max", result.stdout)
        self.assertFalse((self.root / "argv.json").exists(), "Codex ran anyway")
        # A listed pair runs; a model the cache does not know is left to Codex.
        for model, effort in (("gpt-6-luna", "max"), ("gpt-6-sol", "ultra")):
            with self.subTest(model=model, effort=effort):
                self.assertEqual(self.run_worker(model=model, effort=effort).returncode, 0)

    def test_resume_uses_thread_id(self):
        result = self.run_worker("--resume", "t-123")
        self.assertEqual(result.returncode, 0, result.stderr)
        args = json.loads((self.root / "argv.json").read_text(encoding="utf-8"))
        self.assertEqual(args[:3], ["exec", "resume", "t-123"])
        self.assertIn("sandbox_mode=workspace-write", args)
        self.assertNotIn("-s", args)
        self.assert_plugins_disabled(args)

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

    def test_recovered_stream_error_does_not_hide_the_real_failure(self):
        result = self.run_worker(mode="retry-then-crash")
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout.splitlines()[:2],
                         ["Status: BLOCKED", "Unresolved: sandbox setup failed"])

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
        for model in ("x; rm", "gpt-model\n", "-c"):
            with self.subTest(model=repr(model)):
                result = self.run_worker(model=model)
                self.assertEqual(result.returncode, 2)
                self.assertFalse((self.root / "argv.json").exists())

    def test_rejects_bad_resume(self):
        # An option-like id would reach `codex exec resume` as a flag.
        for thread in ("t-123\n", "--dangerously-bypass-approvals-and-sandbox", "-"):
            with self.subTest(thread=repr(thread)):
                result = self.run_worker("--resume", thread)
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

    @unittest.skipIf(os.name == "nt", "POSIX signals; TaskStop kills the whole tree on Windows")
    def test_sigterm_also_stops_codex(self):
        env = os.environ.copy()
        env.update(ORCHESTRA_CODEX_BIN=str(FAKE), FAKE_MODE="hang")
        worker = subprocess.Popen([
            "node", str(WORKER), "--model", "gpt-6-luna", "--effort", "high", "--cwd", str(self.root),
            "--brief", str(self.brief), "--allowed", "a.txt",
        ], cwd=ROOT, env=env, stdout=subprocess.PIPE, text=True, encoding="utf-8")
        self.addCleanup(lambda: worker.poll() is None and worker.kill())
        pid_file = self.root / "pid.txt"
        for _ in range(200):
            if pid_file.exists() and pid_file.read_text(encoding="utf-8"):
                break
            time.sleep(0.05)
        codex_pid = int(pid_file.read_text(encoding="utf-8"))
        self.addCleanup(self.kill_quietly, codex_pid)
        worker.send_signal(signal.SIGTERM)
        out, _ = worker.communicate(timeout=10)
        self.assertIn("Status: BLOCKED", out)
        with self.assertRaises(ProcessLookupError):
            os.kill(codex_pid, 0)

    @staticmethod
    def kill_quietly(pid):
        try:
            os.kill(pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError, AttributeError):
            pass

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
