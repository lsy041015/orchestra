# Dispatching a Codex worker

Part of `orchestra:orchestrator`. Read it before dispatching a task routed to a Codex worker (only when the user asked for Codex).
`<this skill's base directory>` below is the directory of `orchestra:orchestrator`.

**Codex worker**: the main session calls `Bash` directly with
`run_in_background: true` and `timeout: 7200000`, the maximum; the default
stops a background command after 30 minutes. The worker stops Codex itself
after 110 minutes (`ORCHESTRA_CODEX_TIMEOUT_MS` overrides it) and still reports
`Status: BLOCKED` with its `Scope:` line. Set the description to
`[Codex <model>/<effort>] Task N: <title>` and run:

```text
node "<this skill's base directory>/scripts/codex-worker.mjs" --model <model> --effort <effort> --cwd "<project>" --brief "<workspace>/task-N-codex-prompt.md" --allowed "<files>"
```

`--allowed` is a comma-separated list relative to `--cwd`; end an entry with
`/` to allow a whole directory, for example `src/retry.ts,test/fixtures/`.
Use the repository root as `--cwd`. The Codex sandbox writes only inside
`--cwd`, so the brief and report in `<workspace>` must be inside it; the worker
refuses a brief outside `--cwd`. Name subdirectory files in `--allowed`.
When the repository root is the home directory (a dotfiles repository at
`~`, say), the worker refuses that `--cwd` and the scope check prints
`unchecked` for Claude workers too: ask the user to `git init` the project
directory before the first dispatch.

The sandbox blocks all network access by default, including loopback sockets.
Only when the task's tests need sockets or downloads (for example ROS 2/DDS,
localhost servers, package installs), prefix the command with
`ORCHESTRA_CODEX_NETWORK=1` and record `Network: on` for that task in the
ledger.

The worker runs Codex with the user's Codex plugins disabled, so another
workflow's skills and hooks stay out of the task; the user's `config.toml` and
`AGENTS.md` still apply. Fill
`orchestra:subagent-driven-development/implementer-prompt.md` for the task,
append the following Codex rules, and save the brief as
`<workspace>/task-N-codex-prompt.md`:

```text
Never run git commit, push, reset or checkout: the sandbox keeps .git
read-only, and the main session commits after review. Edit only allowed
files. Never leave long-running servers or editors running. Save full test
output to log files next to [REPORT_FILE] and cite their paths. Keep the report
at [REPORT_FILE] to 40 lines or fewer. Return exactly the brief's status
block. Plugin skills are off in this run: where the brief names an
orchestra: skill, follow the brief's own wording.
```

When the background task completes, notify the user and record its
`Codex thread:` output in the ledger.


## Codex prerequisites

Codex tasks require the Codex CLI, a ChatGPT or API login, Git for the scope
check, and Node.js 18 or later. Before the first Codex dispatch, run
`codex --version` and `codex login status`. If either fails, or a run returns
`Status: BLOCKED` because the model or effort is unavailable, show the error
and ask whether to pick another Codex model or route the tier to a Claude
worker. Never switch models silently.
