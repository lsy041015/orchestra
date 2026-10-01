---
name: orchestrator
description: Use in Claude Code when a plan the user approved or asked to execute should be split into difficulty tiers and each tier delegated to a Claude subagent, or to a Codex CLI worker only when the user asks for Codex. Not for Codex-hosted sessions.
---

# Orchestra Orchestrator

This skill extends `orchestra:subagent-driven-development`. The main session keeps
planning, review, re-review, diagnosis, and integration. Workers only implement.
This skill replaces that workflow's worker selection and fix loop.

Claude Code only. In a Codex-hosted session, use
`orchestra:subagent-driven-development` instead.

## 1. Tiered task list

Get a plan first that the user's kickoff approval or an explicit request to execute covers, using `orchestra:writing-plans` if none exists. Then
show the user one compact table:

| # | Task | Tier | Files |
|---|------|------|-------|
| 1 | Clean up constants | Easy | src/const.gd |
| 2 | Inventory UI | Hard (UI) | ui/inventory.tscn, ui/inventory.gd |

Tiers:
- **Easy**: mechanical, single file, no new behavior.
- **Medium**: normal feature or fix with tests.
- **Hard**: cross-file, new architecture inside the plan, tricky logic, or
  judgment about the visual result. Mark UI work `(UI)`.

Keep lookups and few-line edits inline. A larger mechanical one-file task is
Easy, not inline: the Easy route exists to run such work on a cheaper model,
so it replaces `subagent-driven-development`'s keep-inline rule here.

## 2. Model choice

Workers are Claude by default: Easy `claude sonnet/medium`, Medium
`claude sonnet/high`, Hard and UI `claude sonnet/xhigh`. Use a Codex worker only
when the user named Codex in this conversation. Show the mapping on one line and
dispatch; the defaults need no question.

Read `modules/routing.md` when `~/.claude/orchestra.json` or a project
`.orchestra.json` exists, or when the user named Codex. It merges the files by
key, applies Codex values only on request, requires one confirmation for values
that come from the project file, and says when to ask. Record
`Routing: Easy=..., Medium=..., Hard=..., UI=...` in the ledger.

## 3. Dispatch

Label every worker so the task list shows its engine, model, and effort:
`[<Codex|Claude> <model>/<effort>] Task N: <title>`. Reuse a Claude worker
through `SendMessage` for a later task only when that task has the same routing
value, and record the later task's scope baseline first. A reused worker keeps
its first label; the ledger shows its current task.

Claude worker: read `modules/dispatch-claude.md` (agent per effort, scope
baseline before and check after).

Codex worker (only when a task routes to Codex at the user's request): read
`modules/dispatch-codex.md` (background `codex-worker.mjs` run, brief rules, network opt-in, and the prerequisite check before the first
Codex dispatch).

Workers of either engine may run in parallel when their files and state do
not overlap; tier routing is itself the exception to the one-worker default, so
it needs no separate parallel request. The scope check compares the whole
checkout, so a file changed by another worker running at the same time also
appears in `Scope: outside allowed`. Ignore a listed file only when it belongs
to a concurrent worker's allowed list; otherwise treat it as a finding. For the
same reason, do not edit a checkout while a worker runs in it. Separate
worktrees avoid this overlap.

## 4. Review and fix loop

Review every result from the actual diff and read its `Scope:` line. Read
`modules/review-loop.md` for how to treat each `Scope:` result, leftover
processes, the fix loop for either engine, and the two-round limit.

## User controls

The user can confirm tasks from the task list, cancel a task with
`TaskStop <task id>` (this stops the Codex process tree; record the task as
`BLOCKED`), or say "switch Task N to <model>". Finish or stop the current worker
before changing the model, then dispatch again with a fresh brief.
