---
name: orchestrator
description: Use in Claude Code when an approved plan should be split into difficulty tiers and each tier delegated to a Claude subagent or a Codex CLI worker with a user-chosen model and effort. Not for Codex-hosted sessions.
---

# Orchestra Orchestrator

This skill extends `orchestra:subagent-driven-development`. The main session keeps
planning, review, re-review, diagnosis, and integration. Workers only implement.
This skill replaces that workflow's worker selection and fix loop.

Claude Code only. In a Codex-hosted session, use
`orchestra:subagent-driven-development` instead.

## 1. Tiered task list

Get an approved plan first, using `orchestra:writing-plans` if none exists. Then
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

Before asking the user, read `~/.claude/orchestra.json` and `<project>/.orchestra.json`;
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

Routing values have the form `<codex|claude> <model>/<effort>`.
- Claude: `<model>` is a model alias the `Agent` tool accepts (for example
  `sonnet`, `opus`, `haiku`). Effort `high` uses `orchestra:implementer` and
  `medium` uses `orchestra:implementer-medium`.
- Codex: `<model>` is any model your Codex CLI account can use; `<effort>` is
  one of `none`, `minimal`, `low`, `medium`, `high`, `xhigh`, `max`, `ultra`.
  Not every model supports every effort; Codex reports an unsupported pair as a
  failed run.

Use the `ui` key for separately routed UI tasks and `hard` for other hard
tasks; without a `ui` value, UI tasks use `hard`. If a file is not valid JSON
or a value does not match the form, tell the user which one and ask instead of
guessing. If every tier in the task table has
a routing value, skip questions and show the mapping on one line. Ask with
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
| high | `orchestra:implementer` |
| medium | `orchestra:implementer-medium` |

Pass `model` from the routing value. Effort comes from the agent definition;
for another effort, tell the user it needs a new agent file.

**Codex worker**: the main session calls `Bash` directly with
`run_in_background: true` and no `timeout` parameter. Set the description to
`[Codex <model>/<effort>] Task N: <title>` and run:

```text
node "<this skill's base directory>/scripts/codex-worker.mjs" --model <model> --effort <effort> --cwd "<project>" --brief "<ledger>/task-N-codex-prompt.md" --allowed "<files>"
```

`--allowed` is a comma-separated list relative to `--cwd`; end an entry with
`/` to allow a whole directory, for example `src/retry.ts,test/fixtures/`.
Use the repository root as `--cwd`. The Codex sandbox writes only inside
`--cwd`, so the brief and report in `<ledger>` must be inside it; the worker
refuses a brief outside `--cwd`. Name subdirectory files in `--allowed`.

Fill `orchestra:subagent-driven-development/implementer-prompt.md` for the task,
append the following Codex rules, and save the brief as
`<ledger>/task-N-codex-prompt.md`:

```text
Never run git commit, push, reset or checkout: the sandbox keeps .git
read-only, and the main session commits after review. Edit only allowed
files. Never leave long-running servers or editors running. Keep the report
at [REPORT_FILE] to 40 lines or fewer. Return exactly the brief's status
block.
```

When the background task completes, notify the user and record its
`Codex thread:` output in the ledger.

Codex workers may run in parallel when their files do not overlap. The scope
check compares the whole checkout, so a file changed by another worker running
at the same time also appears in `Scope: outside allowed`. Ignore a listed file
only when it belongs to a concurrent worker's allowed list; otherwise treat it
as a finding. Separate worktrees avoid this overlap.

## 4. Review and fix loop

Review every result from the actual diff. After each Codex run:
- Treat `Scope: outside allowed` as a review finding (see the parallel rule
  above). The check does not see `.gitignore`d paths; review those from the
  diff and the worker report when the task touches them.
- `Scope: unchecked (<reason>)` means no mechanical check ran: not a git
  repository, git refused it (for example dubious ownership), or git failed
  after the run. Review `git status` and the whole diff yourself, and tell the
  user why the check was skipped.
- Codex workers never commit. When the plan asks for commits, the main session
  commits each task after its review is clean.
- Check for processes left running from the project directory: on Windows,
  `Get-CimInstance Win32_Process | Where-Object CommandLine -like '*<project>*'`;
  elsewhere, `ps -eo pid,args | grep -F "<project>"`. Ask before stopping a
  process the user may own.

For a Claude worker, send findings to that worker with `SendMessage`. For a
Codex worker, write the follow-up fix described at the end of
`implementer-prompt.md` (each finding with file and location, required
behavior, covering tests, the report instruction) plus the Codex rules to
`<ledger>/task-N-codex-fix-K.md`, then rerun the worker with the same
`--model`, `--effort`, `--cwd` and `--allowed`, plus `--resume <thread>` and
that fix brief. A reply without a status block comes back as
`Status: BLOCKED` (`Codex reply has no status block`); resume the thread with
the missing answer. After two failed fix
rounds with the same root cause, the main session writes a `Ruling:` and
replans or fixes inline.

## Codex prerequisites

Codex tasks require the Codex CLI, a ChatGPT or API login, Git for the scope
check, and Node.js 18 or later. Before the first Codex dispatch, run
`codex --version` and `codex login status`. If either fails, or a run returns
`Status: BLOCKED` because the model or effort is unavailable, show the error
and ask whether to pick another Codex model or route the tier to a Claude
worker. Never switch models silently.

## User controls

The user can confirm tasks from the task list, cancel a task with
`TaskStop <task id>` (this stops the Codex process tree; record the task as
`BLOCKED`), or say "switch Task N to <model>". Finish or stop the current worker
before changing the model, then dispatch again with a fresh brief.
