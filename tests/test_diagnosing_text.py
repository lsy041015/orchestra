#!/usr/bin/env python3
from pathlib import Path
import re
import unittest


SKILL = Path(__file__).resolve().parents[1] / "skills/diagnosing-orchestra"


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


if __name__ == "__main__":
    unittest.main()
