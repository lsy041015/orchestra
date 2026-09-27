---
name: relay-orchestrator
description: Claude Code only. Routes tasks to Claude or Codex workers by difficulty tier.
---

# Relay Orchestrator

This skill extends `relay:subagent-driven-development`. The main session keeps
planning, review, re-review, diagnosis, and integration. Workers only implement.
This skill replaces that workflow's worker selection and fix loop.

## 1. Tiered task list

Get an approved plan first, using `relay:writing-plans` if none exists. Then
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

Keep a one-file edit or a lookup inline instead of listing it.

## 2. Model choice

Before asking the user, read `~/.claude/relay.json` and `<project>/.relay.json`;
ignore either file if it does not exist. Merge `routing` by key, with project
values taking precedence. A project `options` array replaces the user array;
otherwise use the user array. The values use this schema:

```json
{
  "routing": {
    "easy": "codex gpt-6-luna/medium",
    "medium": "claude sonnet/high",
    "hard": "claude opus/high",
    "ui": "claude opus/high"
  },
  "options": ["codex gpt-6-luna/medium", "codex gpt-6-luna/high",
              "claude sonnet/high", "claude opus/high"]
}
```

Routing values have the form `<codex|claude> <model>/<effort>`. Claude supports
`high` (use `relay:implementer`) and `medium` (use
`relay:implementer-medium`). Use the `ui` key for separately routed UI tasks
and `hard` for other hard tasks. If every tier in the task table has a routing
value, skip questions and show the mapping on one line. Ask with
`AskUserQuestion` only for tiers without a value, using the merged `options`
array or the four example choices above when it is absent. The user may enter
another model through `Other`. Record the final mapping in the ledger as
`Routing: Easy=..., Medium=..., Hard=..., UI=...` when UI is a separate tier.

## 3. Dispatch

Label every worker so the task list shows its engine, model, and effort:
`[<Codex|Claude> <model>/<effort>] Task N: <title>`.

**Claude worker**: use the `Agent` tool.

| Effort | subagent_type |
|--------|---------------|
| high | `relay:implementer` |
| medium | `relay:implementer-medium` |

Pass `model` (`opus` / `sonnet` / `haiku`). Effort comes from the agent
definition. For another effort, tell the user it needs a new agent file.

**Codex worker**: the main session calls `Bash` directly with
`run_in_background: true` and no `timeout` parameter. Set the description to
`[Codex <model>/<effort>] Task N: <title>` and run:

```text
node "<this skill's base directory>/scripts/codex-worker.mjs" --model <model> --effort <effort> --cwd "<project>" --brief "<ledger>/task-N-codex-prompt.md" --allowed "<files>"
```

Fill `relay:subagent-driven-development/implementer-prompt.md` for the task,
append the following Codex rules, and save the brief as
`<ledger>/task-N-codex-prompt.md`:

```text
Never run git commit, push, reset or checkout unless the brief says so. Edit
only allowed files. Never leave long-running servers or editors running. Keep
the report at [REPORT_FILE] to 40 lines or fewer. Return exactly the brief's
status block.
```

When the background task completes, notify the user and record its
`Codex thread:` output in the ledger. Codex workers may run in parallel when
their files do not overlap.

## 4. Review and fix loop

Review every result from the actual diff. After each Codex run, check that it
started no stray processes and touched no files outside its allowed list. Treat
`Scope: outside allowed` as a review finding.

For a Claude worker, send findings to that worker. For a Codex worker, write
findings to `<ledger>/task-N-codex-fix-K.md` using the re-review prompt format,
then rerun the worker with the same `--model`, `--effort`, `--cwd` and
`--allowed`, plus `--resume <thread>` and that fix brief. If the scope
is outside allowed, treat it as a review finding before dispatching another
fix. After two failed fix rounds with the same root cause, the main session
writes a `Ruling:` and replans or fixes inline.

## Codex prerequisites

Codex tasks require the Codex CLI, a successful `codex login`, and Node.js 18 or
later. Check `codex --version` before dispatch. If it fails, ask whether to
route the affected Codex tier to a Claude worker.

## User controls

The user can confirm tasks from the task list, cancel a task with
`TaskStop <task id>` (record the task as `BLOCKED`), or say
"switch Task N to <model>". Finish or stop the current worker before changing
the model, then dispatch again with a fresh brief.
