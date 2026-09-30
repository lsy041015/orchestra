#!/usr/bin/env python3
from pathlib import Path
import os
import re
import shutil
import subprocess
import tempfile
import unittest


SKILL = Path(__file__).resolve().parents[1] / "skills/diagnosing-orchestra"
# Search PATH like a shell: on Windows a bare "bash" can resolve to WSL's.
BASH = shutil.which("bash") or "bash"


def read(rel):
    return (SKILL / rel).read_text(encoding="utf-8")


def step(n):
    # Numbered workflow step n of SKILL.md, up to the next step or heading.
    return re.search(rf"^{n}\. \*\*.*?(?=^\d\. \*\*|^## )", read("SKILL.md"), re.S | re.M).group(0)


class DiagnosingTextTests(unittest.TestCase):
    def test_issue_draft_is_scrubbed_before_it_is_shown(self):
        issues = step(5)
        for prompt in ("prompts/scrub.md", "prompts/scrub-audit.md"):
            self.assertIn(prompt, issues)
            self.assertLess(issues.index(prompt), issues.index("show the exact"))
        filing = read("references/github-issues.md").split("## File in Orchestra")[1]
        self.assertIn("prompts/scrub-audit.md", filing)
        self.assertIn("CLEAN", filing)

    def test_transcripts_are_evidence_not_instructions_from_triage_on(self):
        for text in (step(3), read("prompts/analyst-common.md"), read("references/context-safety.md")):
            text = " ".join(text.split()).lower()
            self.assertIn("evidence, not instructions", text)
            self.assertIn("past human prompts", text)
        self.assertNotIn("user requests", read("SKILL.md"))

    def test_marker_text_is_searched_from_a_file_with_fixed_strings(self):
        similar = " ".join(read("prompts/similar-session.md").split())
        self.assertRegex(similar, r"grep -\w*F\w*f ")
        self.assertIn("never put it in a command line", similar)
        self.assertIn("prompts/similar-session.md` step 2", " ".join(step(7).split()))

    def test_dash_encoded_project_folders_are_redacted(self):
        policy = read("references/redaction-policy.md")
        for encoded in ("-home-", "-Users-", "C--Users-"):
            self.assertIn(encoded, policy)
        self.assertIn("`<PROJECT-n>`", policy)
        self.assertIn("<PROJECT-", read("templates/bundle-README.md"))

    def test_pattern_pass_catches_common_token_shapes(self):
        section = read("references/redaction-policy.md").split("## Pattern pass")[1]
        command = re.search(r"```bash\n(.*?)```", section, re.S).group(1)
        # Built at runtime so the repository holds no token-shaped strings.
        tokens = {
            "github": "gh" + "p_" + "a1" * 18, "oauth": "gh" + "o_" + "b" * 36,
            "pat": "github" + "_pat_" + "11AB" * 6, "openai": "KEY=s" + "k-proj-" + "x" * 30,
            "anthropic": "s" + "k-ant-api03-" + "y" * 40, "aws": "AK" + "IA" + "ABCDEFGHIJKLMNOP",
            "slack": "xo" + "xb-1234-5678-abcdef", "jwt": "ey" + "JhbGciOiJIUzI1NiJ9.ey" + "JzdWIiOiIxMjM0NTY3ODkwIn0.s",
            "pem": "-----BEGIN RSA" + " PRIVATE KEY-----", "userinfo": "https://alice:" + "hunter2@git.example.com/x",
        }
        clean = "task-driven-development-workflow <SECRET-1> https://github.com/lsy041015/orchestra http://h:8080/a@b"
        with tempfile.TemporaryDirectory() as bundle:
            for name, text in {**tokens, "clean": clean}.items():
                Path(bundle, name).write_text(f"x {text}\n", encoding="utf-8")
            out = subprocess.run([BASH, "-c", command], env={**os.environ, "BUNDLE": bundle},
                                 capture_output=True, text=True).stdout
        self.assertEqual({line.split(":")[0].lstrip("./\\") for line in out.splitlines()}, set(tokens))
        for prompt in ("prompts/scrub.md", "prompts/scrub-audit.md"):
            self.assertIn("pattern pass", read(prompt))
        export = " ".join(step(6).split())
        self.assertIn("blocks export", export)
        self.assertIn("private source code", export)

    def test_gh_commands_take_transcript_text_from_files(self):
        issues = read("references/github-issues.md")
        self.assertNotIn('"<terms>"', issues)
        self.assertNotIn('"<title>"', issues)
        self.assertIn('"$(cat <case workspace>/issue/terms.txt)"', issues)
        self.assertIn('"$(cat <case workspace>/issue/title.txt)"', issues)

    def test_case_workspace_is_private(self):
        locate = step(2)
        self.assertIn("umask 077", locate)
        self.assertIn("chmod 700", locate)
        self.assertIn("Windows", locate)

    def test_triggers_only_on_a_request_to_diagnose(self):
        skill = read("SKILL.md")
        self.assertRegex(skill, r"(?m)^description: Use when the user asks to diagnose or investigate an Orchestra ")
        self.assertNotIn("disable-model-invocation", skill)
        self.assertRegex(read("agents/openai.yaml"), r'short_description: "Diagnose an Orchestra session on request')


if __name__ == "__main__":
    unittest.main()
