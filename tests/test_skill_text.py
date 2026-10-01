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

    def test_repeated_rules_are_identical(self):
        # Each skill loads on its own, so these rules are restated; one wording keeps them from drifting.
        for rule, least in ((r"the fix-round limit \(([^)]*)\)", 12),
                            (r"`followup_task` \(Codex\) / `SendMessage` \(([^)]*)\)", 8)):
            found = [m for doc in ROOT.glob("skills/**/*.md")
                     for m in re.findall(rule, " ".join(doc.read_text(encoding="utf-8").split()))]
            self.assertGreaterEqual(len(found), least, rule)
            self.assertEqual(len(set(found)), 1, set(found))
        for doc in ROOT.glob("skills/**/*.md"):
            self.assertNotIn("two failed fix attempts", doc.read_text(encoding="utf-8"), doc.relative_to(ROOT))

    def test_orchestrator_runs_on_top_of_sdd(self):
        # The ledger, briefs and final review live only in SDD; the orchestrator must load it.
        read = lambda path: " ".join((ROOT / path).read_text(encoding="utf-8").split())
        self.assertIn("extends `orchestra:subagent-driven-development`: load that skill too", read("skills/orchestrator/SKILL.md"))
        self.assertIn("continue with `orchestra:orchestrator` in Claude Code", read("skills/writing-plans/SKILL.md"))

    def test_implementer_agents_share_one_contract(self):
        # Every /medium and /xhigh route lands on its own agent, so each owes the same report.
        body = lambda name: (ROOT / "agents" / name).read_text(encoding="utf-8").split("\n---\n", 1)[1]
        for other in ("implementer-medium.md", "implementer-xhigh.md"):
            self.assertEqual(body("implementer.md"), body(other), other)

    def test_state_paths_name_the_plan_workspace(self):
        # The ledger is progress.md, a file; briefs and scope states live in its directory.
        for doc in DOCS:
            self.assertNotIn("<ledger>/", doc.read_text(encoding="utf-8"), doc.relative_to(ROOT))

    def test_codex_background_run_sets_the_longest_timeout(self):
        text = (ROOT / "skills/orchestrator/modules/dispatch-codex.md").read_text(encoding="utf-8")
        self.assertIn("`timeout: 7200000`", text)

    def test_inline_task_is_marked_complete_after_its_review(self):
        text = (ROOT / "skills/executing-plans/SKILL.md").read_text(encoding="utf-8")
        self.assertIn("run `task-done`\n  only after the inline review below is clean", text)
        self.assertIn("Run `task-done` after the last fix", text)

    def test_new_project_starts_with_one_kickoff_gate(self):
        # Questions up front for a new project or large feature; afterwards only gaps and consequential choices.
        brain = (ROOT / "skills/brainstorming/SKILL.md").read_text(encoding="utf-8")
        self.assertIn("**Kickoff.**", brain)
        for need in ("deliverable", "success criteria", "constraints", "non-goals"):
            self.assertIn(need, brain)
        self.assertIn("approval", brain.split("**Kickoff.**", 1)[1].split("\n\n", 1)[0])
        self.assertIn("After kickoff, ask only", brain)
        self.assertIn("starting a new project", brain.split("---", 2)[1])
        plans = (ROOT / "skills/writing-plans/SKILL.md").read_text(encoding="utf-8")
        self.assertIn("orchestra:brainstorming", plans.split("## Plan structure", 1)[0])
        orch = (ROOT / "skills/orchestrator/SKILL.md").read_text(encoding="utf-8")
        self.assertIn("kickoff approval", orch)

    def test_finishing_keeps_the_force_push_guard(self):
        text = (ROOT / "skills/finishing-a-development-branch/SKILL.md").read_text(encoding="utf-8")
        self.assertIn("force-push only when", text)

    def test_every_markdown_file_stays_under_300_lines(self):
        # Modules exist so an agent reads one situation's file, not a whole skill.
        for doc in [*ROOT.glob("skills/**/*.md"), *ROOT.glob("agents/*.md")]:
            lines = len(doc.read_text(encoding="utf-8").splitlines())
            self.assertLessEqual(lines, 300, f"{doc.relative_to(ROOT)}: {lines} lines")

    def test_file_map_names_every_skill_and_module_and_every_path_exists(self):
        skills = ROOT / "skills"
        text = (skills / "using-orchestra/references/file-map.md").read_text(encoding="utf-8")
        for doc in [*skills.glob("*/SKILL.md"), *skills.glob("*/modules/*.md")]:
            self.assertIn(str(doc.relative_to(skills)).replace("\\", "/"), text, doc.relative_to(skills))
        for path in re.findall(r"`([a-z][\w./-]*\.md)`", text):
            self.assertTrue((skills / path).exists(), path)
        for doc in skills.glob("*/*/*.md"):
            rel = str(doc.relative_to(skills)).replace("\\", "/")
            self.assertTrue(rel in text or rel.rsplit("/", 1)[0] + "/" in text, f"file map misses {rel}")

    def test_claude_is_the_default_worker_and_codex_needs_a_request(self):
        # Prose wraps, so compare with whitespace collapsed.
        read = lambda path: " ".join((ROOT / path).read_text(encoding="utf-8").split())
        orch, routing = read("skills/orchestrator/SKILL.md"), read("skills/orchestrator/modules/routing.md")
        for default in ("claude sonnet/medium", "claude sonnet/high", "claude sonnet/xhigh"):
            self.assertIn(default, orch)
        for text in (orch, routing):
            self.assertIn("only when the user named Codex", text)
        self.assertIn("only when the user asks for Codex", orch.split("---", 2)[1])
        schema = routing.split("```json", 1)[1].split('"options"', 1)[0]
        self.assertNotIn("codex", schema.lower())
        self.assertIn("never offer codex", routing.lower())



if __name__ == "__main__":
    unittest.main()
