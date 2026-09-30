# Claude Code Tool Notes

Skills describe actions in prose. Follow the actual tool list and current
host rules when translating them to Claude Code calls; this document is
guidance, not an API contract.

## One delegated role

The main session keeps the user's selected model and reasoning effort and owns
planning, exploration, diagnosis, review, re-review, integration, and final
verification. A delegated call is for a bounded implementation worker only.
Do not dispatch a reviewer, analyst, planner, explorer, or nested helper.

Load `orchestra:*` skills with the `Skill` tool. The worker is the plugin agent
`orchestra:implementer`, whose definition sets `model: sonnet` and
`effort: high`; `orchestra:implementer-medium` is the same contract at medium
effort. Dispatch it explicitly:

```text
Agent(
  subagent_type="orchestra:implementer",
  description="Implement task 2",
  prompt="<goal, exact scope, acceptance checks, tests, and report path>"
)
```

Without `orchestra:orchestrator`, do not pass a `model` override; the agent
definition sets Sonnet / high. When the orchestrator is active, follow its
routing instead: it passes `model`, picks the agent by effort, and runs Codex
tiers through `codex-worker.mjs` in a background `Bash` call. The worker
starts with no conversation history, so the prompt must be the complete brief.
If the agent type is unavailable, never silently substitute another agent:
continue inline in the main session and report the limit.

## Fixes and lifecycle

Record the worker's agent id/name. When the main agent's review finds a
concrete defect, send the finding to the same worker with `SendMessage`;
include the file, location, failure, acceptance condition, and covering test.
A Codex CLI worker is a background `Bash` task that `SendMessage` cannot
reach; follow the orchestrator's fix brief and `--resume <thread>` instead.
A follow-up is a new implementation turn, not a new review seat. The worker
appends its result and test evidence to the report. The main agent reviews the
actual fix diff again.

If two failed fix attempts have the same root cause, stop retrying. The main
agent changes the diagnosis or plan, or fixes the small issue inline; do not
create a fresh worker merely to obtain different eyes. Explicitly requested
independent parallel implementation is one exception to the one-worker
default: send multiple `Agent` calls in one message, each `orchestra:implementer`
with disjoint files and state. The orchestrator's tier routing is the other.

## Waiting and evidence

Agents run in the background by default and notify on completion; do not
poll. Meanwhile, do only work that leaves the worker's checkout untouched: the
orchestrator's scope check would count your edit against the worker. Do not
treat an unverified worker summary as proof: inspect the actual diff, affected
call paths, and reported test output.

## Environment and workspace

Before using worktree or branch operations, use read-only git inspection to
distinguish a linked worktree, an ordinary checkout, and detached HEAD. Apply
`orchestra:using-git-worktrees` for isolation and preserve unrelated user changes.
Do not delete a workspace or alter a shared branch without authorization.
