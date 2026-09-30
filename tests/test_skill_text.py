#!/usr/bin/env python3
from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
DOCS = sorted([*ROOT.glob("README*.md"), *ROOT.glob("agents/*.md"),
               *ROOT.glob("skills/**/*.md"), *ROOT.glob("docs/**/*.md")])
FENCE = re.compile(r"^[ \t]*(`{3,}|~{3,})[^\n]*\n.*?^[ \t]*\1[ \t]*$", re.S | re.M)


class SkillTextTests(unittest.TestCase):
    def test_orchestra_references_resolve(self):
        names = {p.name for p in (ROOT / "skills").iterdir()} | {p.stem for p in ROOT.glob("agents/*.md")}
        for doc in DOCS:
            for name in re.findall(r"orchestra:([a-z][a-z0-9-]*)", doc.read_text(encoding="utf-8")):
                self.assertIn(name, names, f"{doc.relative_to(ROOT)}: orchestra:{name}")

    def test_relative_links_resolve(self):
        for doc in DOCS:
            # Skip fenced examples, URLs (scheme:) and same-page anchors (#...).
            text = FENCE.sub("", doc.read_text(encoding="utf-8"))
            for target in re.findall(r"\]\((?![A-Za-z][\w+.-]*:)([^)\s#]+)", text):
                self.assertTrue((doc.parent / target).exists(), f"{doc.relative_to(ROOT)}: {target}")

    def test_host_preset_is_identical_and_matches_agent(self):
        presets = set()
        for doc in ROOT.glob("skills/**/*.md"):
            presets.update(re.findall(r"the host implementer preset \(([^)]*)\)", doc.read_text(encoding="utf-8")))
        self.assertEqual(len(presets), 1, presets)
        agent = (ROOT / "agents/implementer.md").read_text(encoding="utf-8")
        model = re.search(r"^model: (\S+)$", agent, re.M).group(1)
        effort = re.search(r"^effort: (\S+)$", agent, re.M).group(1)
        self.assertIn(f"`orchestra:implementer` agent = `{model}` / `{effort}`", presets.pop())

    def test_implementer_agents_share_one_contract(self):
        # Every /medium route lands on implementer-medium, so it owes the same report.
        body = lambda name: (ROOT / "agents" / name).read_text(encoding="utf-8").split("\n---\n", 1)[1]
        self.assertEqual(body("implementer.md"), body("implementer-medium.md"))

    def test_state_paths_name_the_plan_workspace(self):
        # The ledger is progress.md, a file; briefs and scope states live in its directory.
        for doc in DOCS:
            self.assertNotIn("<ledger>/", doc.read_text(encoding="utf-8"), doc.relative_to(ROOT))

    def test_codex_background_run_sets_the_longest_timeout(self):
        text = (ROOT / "skills/orchestrator/SKILL.md").read_text(encoding="utf-8")
        self.assertIn("`timeout: 7200000`", text)

    def test_inline_task_is_marked_complete_after_its_review(self):
        text = (ROOT / "skills/executing-plans/SKILL.md").read_text(encoding="utf-8")
        self.assertIn("run `task-done`\n  only after the inline review below is clean", text)
        self.assertIn("Run `task-done` after the last fix", text)


if __name__ == "__main__":
    unittest.main()
