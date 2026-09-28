#!/usr/bin/env python3
"""The visual companion stays local and keeps its session files out of git."""
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

# Search PATH like a shell: on Windows a bare "bash" can resolve to WSL's
# System32\bash.exe before Git Bash.
BASH = shutil.which("bash") or "bash"

SCRIPTS = Path(__file__).resolve().parents[1] / "skills/brainstorming/scripts"


class BrainstormCompanionTests(unittest.TestCase):
    def test_frame_loads_nothing_remote(self):
        page = subprocess.run(
            ["node", "-e", "process.stdout.write(require(process.argv[1]).wrapInFrame('<p>x</p>'))",
             str(SCRIPTS / "server.cjs")],
            check=True, capture_output=True, text=True, encoding="utf-8").stdout
        self.assertIn("Orchestra", page)
        self.assertNotIn("Superpowers", page)
        # The only absolute URL left is the project link.
        self.assertEqual(set(re.findall(r"https?://[^\s\"'<>)]+", page)),
                         {"https://github.com/lsy041015/orchestra"})

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
                                              f".superpowers/brainstorm/{name}"])
                    self.assertEqual(ignored.returncode, 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
