# Orchestra file map

Which file to read in which situation. Paths are relative to `skills/` (script paths such as `scripts/...` are relative to their own skill).

Rules:
- Read the `SKILL.md` of the skill that fires, nothing else of that skill, until
  one of its rows below applies. Never read a whole skill directory.
- Every markdown file under `skills/` and `agents/` is at most 300 lines; a test enforces it.
- Files under `scripts/` are run, not read. Read one only to debug it.

## Entry

| Situation | Read |
|---|---|
| Starting an Orchestra workflow that needs planning, handoff or review | `using-orchestra/SKILL.md` |

## Design and planning

| Situation | Read |
|---|---|
| New project, or large feature without a spec or plan | `brainstorming/SKILL.md` |
| Architectural change (new subsystem, migration, cross-component interface) | `brainstorming/references/architecture.md` |
| User asks for the browser visual companion | `brainstorming/visual-companion.md` |
| Settled design needs multiple verifiable steps | `writing-plans/SKILL.md` |

## Execution

| Situation | Read |
|---|---|
| Claude Code, plan split into difficulty tiers | `orchestrator/SKILL.md` |
| A routing config file exists or the user named Codex | `orchestrator/modules/routing.md` |
| Dispatching a task to a Claude worker | `orchestrator/modules/dispatch-claude.md` |
| Dispatching a task to a Codex worker | `orchestrator/modules/dispatch-codex.md` |
| A worker result is ready to review or fix | `orchestrator/modules/review-loop.md` |
| Delegated plan execution: setup, ledger, briefs, review, final review (Claude Code loads it with the orchestrator) | `subagent-driven-development/SKILL.md` |
| Writing the worker brief | `subagent-driven-development/implementer-prompt.md` |
| Task review or re-review of a worker result | `subagent-driven-development/task-reviewer-prompt.md`, `subagent-driven-development/re-review-prompt.md` |
| Executing an approved plan inline, no workers | `executing-plans/SKILL.md` |
| User explicitly asks for parallel independent work | `dispatching-parallel-agents/SKILL.md` |
| Exact tool syntax on this host | `using-orchestra/references/claude-code-tools.md` or `using-orchestra/references/codex-tools.md` (one) |

## Isolation, quality, review

| Situation | Read |
|---|---|
| Task needs an isolated checkout | `using-git-worktrees/SKILL.md` |
| No native worktree tool is usable | `using-git-worktrees/modules/git-worktree-fallback.md` |
| Adding or changing behavior, fixing a bug | `test-driven-development/SKILL.md` |
| Writing or reviewing tests in detail | `test-driven-development/writing-good-tests.md` |
| Bug, failing test, unexpected behavior | `systematic-debugging/SKILL.md` |
| Tracing a bug up the call stack | `systematic-debugging/root-cause-tracing.md` |
| Adding validation after the root cause is found | `systematic-debugging/defense-in-depth.md` |
| Arbitrary sleeps or timeouts in tests | `systematic-debugging/condition-based-waiting.md` |
| About to claim work is done or passing | `verification-before-completion/SKILL.md` |
| Asking for a review of finished work | `requesting-code-review/SKILL.md`, then `requesting-code-review/code-reviewer.md` |
| Review feedback arrived | `receiving-code-review/SKILL.md` |

## Finishing

| Situation | Read |
|---|---|
| Work is complete and must be integrated | `finishing-a-development-branch/SKILL.md` |
| User chose Option 1, merge locally | `finishing-a-development-branch/modules/merge-locally.md` |
| User explicitly asked to discard the work | `finishing-a-development-branch/modules/discard.md` |
| Option 1 or a confirmed discard (Step 6) | `finishing-a-development-branch/modules/cleanup-workspace.md` |

## Maintaining Orchestra

| Situation | Read |
|---|---|
| Creating or editing a skill | `writing-skills/SKILL.md`, then at most the part of `writing-skills/best-practices/` it names |
| User asks to diagnose an Orchestra session | `diagnosing-orchestra/SKILL.md`, then only the `diagnosing-orchestra/references/`, `diagnosing-orchestra/prompts/` and `diagnosing-orchestra/templates/` files its steps name |
