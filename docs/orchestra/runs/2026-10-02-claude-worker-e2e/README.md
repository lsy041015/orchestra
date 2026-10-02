# Claude-worker default path: one real end-to-end run (2026-10-02)

Until this run, `CHANGELOG.md` said the default Hard/UI tier
(`orchestra:implementer-xhigh`) "has not yet been dispatched in a real run", and
no recorded run covered the Claude-worker defaults of 0.4.6 and later. This is
that run: orchestra 0.4.9 as installed from the plugin cache, Claude Code 2.1.286,
a Sonnet 5.5 main session, a throwaway Python repo outside any other repository.

`plan.md` is the plan, `ledger.md` is the SDD ledger the run produced. The plan is
small on purpose; it is a smoke test you can repeat, not a benchmark.

## What ran

Defaults only, no question asked: Easy `claude sonnet/medium`, Medium
`claude sonnet/high`, Hard `claude sonnet/xhigh`. Per task: `sdd-workspace`,
`task-brief`, `scope-check.mjs before`, an `Agent` dispatch with the implementer
prompt, `scope-check.mjs after`, main-session review from the diff plus own probes.

| Task | Tier | Agent (`subagent_type`) | Result |
|------|------|-------------------------|--------|
| 1 Constants | Easy | `orchestra:implementer-medium` | DONE, 1 commit |
| 2 Cart | Medium | `orchestra:implementer` | DONE, 12 tests, RED then GREEN logs |
| 3 Discounts | Hard | `orchestra:implementer-xhigh` | DONE, 31 tests; worker ran 4 mutants against its own suite |
| 3 fix 1 | Hard | same worker, resumed with `SendMessage` | DONE, 32 tests |

## Evidence that the right agent, model and effort ran

Each subagent's transcript is `~/.claude/projects/<project>/<session>/subagents/agent-<id>.jsonl`
(plus `.meta.json` with `agentType`). Its `assistant` records carry `message.model`
and `effort`. Counted over all assistant turns of each worker:

| Worker | `agentType` | `model` | `effort` |
|--------|-------------|---------|----------|
| Task 1 | `orchestra:implementer-medium` | `claude-sonnet-5-5` | `medium` (4 turns) |
| Task 2 | `orchestra:implementer` | `claude-sonnet-5-5` | `high` (11 turns) |
| Task 3 | `orchestra:implementer-xhigh` | `claude-sonnet-5-5` | `xhigh` (16 turns; 24 after the `SendMessage` resume) |

So `sonnet` resolves to Sonnet 5.5 and accepts `xhigh`; no other model was
substituted, and the effort survived a resume. This shows the setting was applied.
It does not show that xhigh did better work than high on this task.

## What the review found

- Task 3 passed the first review (every plan rule probed, including stacking in both
  orders, the 50% cap and half-cent rounding). The worker itself flagged that a
  sub-cent line could end with a tiny negative remaining value, and the ledger first
  recorded that as a plan gap bounded by the cap.
- A probe of that case showed it was worse: two `PercentOff` rules on one sub-cent line
  made the second discount negative, which cancelled the first, so the total
  discount came out `0.00` instead of `0.01`. The main session wrote a `Ruling:`
  (clamp every rule to the line's remaining value) and sent it to the same worker
  with `SendMessage`. The worker added a failing test, fixed it, and the
  re-review passed. This exercised the fix loop of `review-loop.md` once.
- `scope-check` behaved as documented: `Scope: baseline recorded`, `outside allowed`
  with `(ignored)` for `__pycache__/`, and exit code 1 on `outside allowed`.

## Friction and deviations

- The plan had no `.gitignore`, so the first task's `src/__pycache__/` came back as
  `outside allowed` without `(ignored)`. `review-loop.md` calls caches expected only
  when they are ignored. I added `__pycache__/` to `.git/info/exclude` and went on.
  Python plans need an ignore step before the first baseline.
- `~/.claude/orchestra.json` existed, and `orchestrator/SKILL.md` says to read
  `modules/routing.md` then. I did not; the file's `easy` entry is `codex`, which is
  inert until the user names Codex, so the defaults were the same.
- No worktree (the throwaway repo is its own isolation), no finishing step, and the
  whole-branch package was built with `review-package` but not reviewed.

## Not covered

The Codex worker path, parallel workers, a real (non-toy) codebase, UI-tier
dispatch (it routes to the same agent as Hard), the fix-round limit, Windows and
macOS, and any comparison of worker quality across tiers.

## Repeat it

Copy `plan.md` into an empty git repo (set `user.name` and `user.email`), run the
orchestrator on it, then check each worker's transcript with the table above.
