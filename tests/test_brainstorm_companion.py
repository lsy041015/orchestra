#!/usr/bin/env python3
"""The visual companion stays local and keeps its session files out of git."""
from pathlib import Path
import http.cookiejar
import json
import os
import re
import shutil
import subprocess
import tempfile
import time
import unittest
import urllib.parse
import urllib.request

# Search PATH like a shell: on Windows a bare "bash" can resolve to WSL's
# System32\bash.exe before Git Bash.
BASH = shutil.which("bash") or "bash"

SCRIPTS = Path(__file__).resolve().parents[1] / "skills/brainstorming/scripts"


def frame(content):
    return subprocess.run(
        ["node", "-e", "process.stdout.write(require(process.argv[1]).wrapInFrame(process.argv[2]))",
         str(SCRIPTS / "server.cjs"), content],
        check=True, capture_output=True, text=True, encoding="utf-8").stdout


class BrainstormCompanionTests(unittest.TestCase):
    def test_frame_loads_nothing_remote(self):
        page = frame("<p>x</p>")
        self.assertIn("Orchestra", page)
        self.assertNotIn("Superpowers", page)
        # The only absolute URL left is the project link.
        self.assertEqual(set(re.findall(r"https?://[^\s\"'<>)]+", page)),
                         {"https://github.com/lsy041015/orchestra"})

    def test_frame_keeps_dollar_patterns_literal(self):
        content = "<p>costs $$5, keeps $& and $' as typed</p>"
        self.assertIn(content, frame(content))

    def test_choice_api_sends_the_field_the_server_records(self):
        # server.cjs writes only events that carry `choice` to state/events.
        script = """
const sent = [];
global.window = { location: { protocol: 'http:', host: 'localhost' } };
global.document = { querySelector: () => null, addEventListener() {} };
global.WebSocket = class { constructor() { this.readyState = 1; } send(data) { sent.push(JSON.parse(data)); } };
global.WebSocket.OPEN = 1;
require(process.argv[1]);
window.brainstorm.choice('b', { note: 'second' });
process.stdout.write(JSON.stringify(sent));
"""
        out = subprocess.run(["node", "-e", script, str(SCRIPTS / "helper.js")], check=True,
                             capture_output=True, text=True, encoding="utf-8").stdout
        event = json.loads(out)[0]
        self.assertEqual((event["type"], event.get("choice"), event["note"]), ("choice", "b", "second"))

    def test_option_without_value_fails_fast(self):
        result = subprocess.run([BASH, str(SCRIPTS / "start-server.sh"), "--project-dir"],
                                capture_output=True, text=True, encoding="utf-8", timeout=20)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("error", result.stdout)

    def test_project_session_files_are_gitignored(self):
        with tempfile.TemporaryDirectory(prefix="brainstorm-") as temp:
            project = Path(temp)
            subprocess.run(["git", "init", "-q", str(project)], check=True)
            # An address this host does not own makes the server exit right after setup.
            subprocess.run([BASH, str(SCRIPTS / "start-server.sh"), "--project-dir", str(project),
                            "--host", "203.0.113.1", "--foreground"],
                           capture_output=True, text=True, encoding="utf-8", timeout=60)
            for name in (".last-token", ".last-port", "session/state/server-info"):
                with self.subTest(name=name):
                    ignored = subprocess.run(["git", "-C", str(project), "check-ignore", "-q",
                                              f".orchestra/brainstorm/{name}"])
                    self.assertEqual(ignored.returncode, 0)

    def serve(self, cwd, args, env=None, info_glob=None):
        """Start a real companion, return its server-info and session dir."""
        proc = subprocess.Popen([BASH, str(SCRIPTS / "start-server.sh"), *args, "--foreground",
                                 "--idle-timeout-minutes", "1"],
                                cwd=cwd, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.addCleanup(lambda: proc.poll() is None and proc.kill())
        for _ in range(200):
            found = list(Path(info_glob[0]).glob(info_glob[1]))
            if found:
                info = json.loads(found[0].read_text(encoding="utf-8"))
                session = found[0].parent.parent
                self.addCleanup(self.stop, session, proc)
                return info, session
            time.sleep(0.1)
        self.fail(f"no server-info under {info_glob}")

    def stop(self, session, proc):
        subprocess.run([BASH, str(SCRIPTS / "stop-server.sh"), str(session)], capture_output=True)
        try:
            proc.wait(timeout=20)
        except subprocess.TimeoutExpired:
            proc.kill()

    def temp_dir(self, prefix):
        # Registered before serve(), so its cleanup runs after the server stops
        # (cleanups run last-in, first-out) and the PID file is still there.
        temp = tempfile.TemporaryDirectory(prefix=prefix)
        self.addCleanup(temp.cleanup)
        return Path(temp.name)

    def test_relative_project_dir_and_encoded_file_names(self):
        project = self.temp_dir("brainstorm-rel-")
        info, _ = self.serve(project, ["--project-dir", "."],
                             info_glob=(project, ".orchestra/brainstorm/*/state/server-info"))
        (Path(info["screen_dir"]) / "my logo.txt").write_text("hello", encoding="utf-8")
        opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
        opener.open(info["url"], timeout=10).read()
        base = info["url"].split("?")[0].rstrip("/")
        body = opener.open(base + "/files/my%20logo.txt", timeout=10).read().decode("utf-8")
        self.assertEqual(body, "hello")

    def test_stop_leaves_an_unidentified_live_process_alone(self):
        # A live PID without this session's server id may be an unrelated
        # process (PID reuse) or the server on a host whose ps hides arguments.
        session = self.temp_dir("brainstorm-stop-")
        state = session / "state"
        state.mkdir()
        (state / "server-instance-id").write_text("a" * 32 + "\n", encoding="utf-8")
        pid_file = state / "server.pid"
        other = subprocess.Popen([BASH, "-c", 'echo $$ > "$1"; exec sleep 30', "_", str(pid_file)])
        for _ in range(100):
            if pid_file.exists() and pid_file.read_text(encoding="utf-8").strip():
                break
            time.sleep(0.05)
        pid = pid_file.read_text(encoding="utf-8").strip()
        self.addCleanup(other.kill)
        self.addCleanup(subprocess.run, [BASH, "-c", 'kill "$1" 2>/dev/null', "_", pid])
        result = subprocess.run([BASH, str(SCRIPTS / "stop-server.sh"), str(session)],
                                capture_output=True, text=True, encoding="utf-8")
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn('"unverified"', result.stdout)
        self.assertTrue(pid_file.exists())
        self.assertFalse((state / "server-stopped").exists())
        self.assertIsNone(other.poll(), "stop-server signalled a process it could not identify")

    def test_temporary_session_is_private_and_removed_on_stop(self):
        tmp = self.temp_dir("brainstorm-tmp-")
        env = {**os.environ, "TMPDIR": str(tmp).replace("\\", "/")}
        _, session = self.serve(tmp, [], env=env, info_glob=(tmp, "brainstorm-*/state/server-info"))
        # mktemp's random suffix, not the guessable "$$-<time>" name.
        self.assertRegex(session.name, r"^brainstorm-[A-Za-z0-9]{6,}$")
        subprocess.run([BASH, str(SCRIPTS / "stop-server.sh"), str(session)], capture_output=True)
        for _ in range(50):
            if not session.exists():
                break
            time.sleep(0.1)
        self.assertFalse(session.exists())

    def test_url_names_the_bound_address(self):
        # "localhost" may resolve to ::1 first, where another local user can
        # listen on our port and receive the key.
        for args, want in (([], "127.0.0.1"), (["--host", "localhost"], None),
                           (["--url-host", "example.test"], "example.test")):
            with self.subTest(args=args):
                tmp = self.temp_dir("brainstorm-url-")
                env = {**os.environ, "TMPDIR": str(tmp).replace("\\", "/")}
                info, _ = self.serve(tmp, args, env=env, info_glob=(tmp, "brainstorm-*/state/server-info"))
                host = urllib.parse.urlsplit(info["url"]).hostname
                if want:
                    self.assertEqual(host, want)
                else:
                    self.assertIn(host, ("127.0.0.1", "::1"))
                    self.assertEqual(urllib.request.urlopen(info["url"], timeout=10).status, 200)


if __name__ == "__main__":
    unittest.main(verbosity=2)
