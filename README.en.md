<p align="center">
  <img src="assets/orchestra-banner.png" alt="Orchestra — Claude × Codex" width="100%">
</p>

<p align="center"><a href="README.md">한국어</a> · <b>English</b></p>

<p align="center"><a href="https://github.com/lsy041015/orchestra/actions/workflows/tests.yml"><img src="https://github.com/lsy041015/orchestra/actions/workflows/tests.yml/badge.svg" alt="tests"></a></p>

# Orchestra

> **The conductor plans. The right model plays.**
> Your Claude Code main session plans and reviews; each bounded implementation task goes to a
> **Claude subagent** by difficulty tier. A **Codex CLI (GPT)** worker is used only when you ask for Codex.

A personal fork of [Superpowers](https://github.com/obra/superpowers) 6.4.1 by Jesse Vincent.
Not an official OpenAI, Anthropic or Superpowers release. Names such as Claude and Codex only indicate
the tools this plugin works with; the marks belong to their owners.

> **Status: experimental (v0.4.6).** See the [changelog](CHANGELOG.md). Used daily on Windows; tests run in CI on Ubuntu, macOS and
> Windows. The full orchestrator flow was recorded once on Linux; macOS use is not recorded yet, and no usage savings are claimed. See [Verification and limits](#verification-and-limits).

## Why

If you pay for both Claude and ChatGPT (Codex), one quota tends to run out while the other goes unused,
and the most expensive model ends up doing mechanical edits. Orchestra keeps judgment in one place and
spends each subscription where it fits:

1. **The main session owns judgment.** Planning, review, diagnosis and integration never leave it, and
   the plugin never changes its model or reasoning effort.
2. **Workers only implement**, one bounded task each, inside an explicit list of allowed files.
   Claude workers cannot start subagents (`disallowedTools: Agent`); for Codex workers that is a brief
   rule, because Codex 0.156 keeps its agent tools even with `features.multi_agent=false`. Codex
   workers never commit; the main session commits after review.
3. **Every result is checked against evidence**: the real diff, real test output, and a mechanical
   scope check (run by the Codex worker itself, and by the main session around a Claude worker with
   `scope-check.mjs`).

## How it works

```text
request → plan (orchestra:writing-plans)
        → tier table   | # | Task | Tier | Files |
        → routing      ~/.claude/orchestra.json + <project>/.orchestra.json, Claude by default, Codex only on request
        → dispatch     Claude: Agent(orchestra:implementer, model=…)
                       Codex:  node codex-worker.mjs … (background Bash)
        → review       diff + tests + Scope line → fix loop (same worker / --resume <thread>)
        → ledger       Task N: complete → final verification → commit (push only after you confirm)
```

Tiers: **Easy** (mechanical, one file), **Medium** (normal feature or fix with tests), **Hard**
(cross-file or tricky logic), **Hard (UI)** (needs visual judgment). Lookups and few-line edits stay
inline; a larger mechanical task is Easy even in one file, so a cheaper model runs it.

Workers show up in the Claude Code task list with their engine, model and effort, e.g.
`[Codex gpt-6-luna/high] Task 3: retry helper`. Cancel one with `TaskStop`, or say
"switch Task 3 to claude opus". A Claude worker takes a later task through `SendMessage` only
when that task has the same routing value, after a fresh scope baseline. It keeps its first label;
the ledger shows which task it is on.

Each brief holds one task plus the plan's `Global constraints` and `Interfaces` sections; the
sections after the tasks (verification, review focus) stay with the main session.

Skills are called `orchestra:<skill>`: 16 skills plus the two Claude implementer agents. Start with
`orchestra:using-orchestra`; `orchestra:orchestrator` does the tiering and dispatch (Claude Code
only) and `orchestra:diagnosing-orchestra` investigates a past run. Plans are saved under
`docs/orchestra/plans/`; each plan's ledger, briefs and reports live in `.orchestra/sdd/<plan>/`.

## A real run

<p align="center"><img src="docs/demo/piano/piano-demo.gif" alt="A web piano built by Orchestra playing Ode to Joy" width="640"></p>

One unedited end-to-end run: a one-octave web piano ([`examples/piano/`](examples/piano/)) split
into three tasks and routed to three Codex workers (`gpt-6-luna/medium`, `gpt-6-sol/medium`,
`gpt-6-sol/high`), two of them in parallel, 13 min 28 s of worker time. Every worker reported
`DONE`, and main-session review still found five issues: a plan gap, a wrong verification command,
doubled key borders, a console error, and invisible repeated notes. Each task needed one
`--resume` fix round. Timeline, findings, browser checks and Codex token usage are in the
[run record](docs/demo/piano/README.md) (Korean).

The same plan was then rebuilt with **Claude workers only** ([comparison](docs/demo/piano/comparison.md), Korean).
Both results passed the same checks in similar time (12 min 26 s vs 13 min 28 s), and the Claude run needed one fewer fix round.
The Codex run used no Claude quota for workers and under 1% of the 7-day Codex quota. That is one run each, not a general saving.

A third run on Linux with 0.4.0 ([record](docs/demo/piano/linux-run/README.md), Korean) finished with no fix round in 7 min 2 s of
worker time. An independent check then found the two issues runs A and B had fixed: the tests fail on Node 18, and a repeated note's
second strike is not visible.

## Install

Requirements: Claude Code, Git + Bash (Git Bash on Windows), Python 3 for the tests, and for Codex
workers Node.js 18+ and a logged-in Codex CLI (`codex --version`, `codex login status`).
Claude Code's Bash tool uses Git Bash on Windows. In PowerShell a bare `bash` may be the WSL
launcher, which fails without a distribution, so run scripts there as
`& 'C:\Program Files\Git\bin\bash.exe' <script>`.

```bash
claude plugin marketplace add lsy041015/orchestra
claude plugin install orchestra@orchestra
```

Start a new session afterwards. Update with `claude plugin marketplace update orchestra` and then
`claude plugin update orchestra@orchestra`.

Codex as the host (shared skills only; `orchestrator` is Claude Code only):

```bash
codex plugin marketplace add lsy041015/orchestra
codex plugin add orchestra@orchestra
```

Do not enable the original Superpowers plugin or the earlier `relay` plugin at the same time; skill names collide.

## Routing config

```json
{
  "routing": {
    "easy":   "claude sonnet/medium",
    "medium": "claude sonnet/high",
    "hard":   "claude sonnet/xhigh",
    "ui":     "claude sonnet/xhigh"
  },
  "options": ["claude sonnet/high", "claude sonnet/xhigh", "claude opus/high",
              "codex gpt-6-luna/medium", "codex gpt-6-luna/high"]
}
```

- `~/.claude/orchestra.json` holds your defaults; `<project>/.orchestra.json` overrides them per key.
  A project `options` array replaces yours.
- Values are `<codex|claude> <model>/<effort>`.
  - Claude: an `Agent` model alias (`sonnet`, `opus`, `haiku`). Effort `high` →
    `orchestra:implementer`, `medium` → `orchestra:implementer-medium`, `xhigh` →
    `orchestra:implementer-xhigh`.
  - Codex: any model your account can use. Effort is one of `none`, `minimal`, `low`, `medium`,
    `high`, `xhigh`, `max`, `ultra`. Support varies by model: when Codex's model cache
    (`$CODEX_HOME/models_cache.json`, default `~/.codex`) lists the model without that effort, the worker stops with
    `Status: BLOCKED` before Codex runs; any other unsupported pair comes back as `Status: BLOCKED`
    with Codex's own message.
- Orchestra shows the mapping and starts; a tier without a value uses the Claude default above.
  `codex` values and options apply only when you named Codex in the conversation, and Codex is never
  offered otherwise. It asks only when you routed a tier to Codex that has no codex value. When any value comes from a project `.orchestra.json`, it shows the
  mapping and asks once before the first dispatch, because a cloned repository's file spends your
  quota.

## Codex worker

```text
node skills/orchestrator/scripts/codex-worker.mjs \
  --model gpt-6-luna --effort high --cwd "<project>" \
  --brief "<workspace>/task-3-codex-prompt.md" \
  --allowed "src/retry.ts,test/retry.test.ts,test/fixtures/" [--resume <thread_id>]
```

`<workspace>` is the plan folder `sdd-workspace` prints (`.orchestra/sdd/<plan>/`).

- Runs `codex exec --json … -s workspace-write --disable plugins` directly and passes the brief on
  stdin. Your Codex plugins (another Superpowers, say) stay off in worker runs so their skills and
  hooks do not bring a different workflow; `config.toml` and `AGENTS.md` still apply. Paths never
  go through a shell, and every value that reaches the Windows shell is validated first. On Windows it also stops the current directory from being searched first, so a
  `codex.cmd` or `git.exe` inside the project never runs in place of the real tool. SIGINT, SIGTERM
  and SIGHUP sent to the worker are passed on to Codex.
- Use the repository root as `--cwd`. The sandbox writes only inside `--cwd` and keeps `.git`
  read-only, so the brief (and the report next to it) must be inside `--cwd`, and Codex workers
  cannot commit. On Linux (Codex 0.156.1) `/tmp` stays writable too. `--allowed` is relative to `--cwd`; an entry ending in `/` allows that whole directory.
- Network is off by default, loopback sockets included. Only when a task's tests need sockets or
  downloads (ROS 2/DDS, localhost servers, package installs), prefix the command with
  `ORCHESTRA_CODEX_NETWORK=1`; the worker then adds `-c sandbox_workspace_write.network_access=true`.
- Output: Codex's final message (the status block), then `Codex thread: <id>` and
  `Scope: ok | outside allowed: <repo-relative paths> | unchecked (<reason>)`. Any git failure
  (not a repository, dubious ownership, a failure after the run) is reported as `unchecked`, never `ok`.
- Failures (non-zero exit, `turn.failed`, no message, no `Status:` line in the reply) become
  `Status: BLOCKED` with a one-line reason and exit 1. An `error` event alone is not a failure;
  Codex also reports recovered stream retries that way, and a recovered one never replaces the
  real reason. Bad arguments exit 2 without starting Codex.
- The scope check ([`scope-check.mjs`](skills/orchestrator/scripts/scope-check.mjs)) hashes
  `git status` entries and records `HEAD` before and after the run, so files you had already
  modified are only flagged if the worker changes them, and committed files still count. It works
  on the physical path, so a symlinked `--cwd` checks the repository git sees. It cannot see
  `.gitignore`d paths, and parallel workers in the same checkout see each other's files; the
  orchestrator ignores only files that belong to another running worker's allowed list.
- For a Claude worker the main session runs the same check:
  `node scope-check.mjs before --cwd <project> --state <workspace>/task-N-scope.json` before dispatch,
  and `after … --allowed <files>` before each review.

## Verification and limits

Checked on 2026-09-27, Windows 11, Codex CLI 0.156.1 (ChatGPT login). The model and effort that were
actually applied were read from Codex's session log (`turn_context`).

| Case | Result |
|---|---|
| Full orchestrator flow (plan → dispatch → review → fix → ledger) | ✅ once with Codex workers and once with Claude workers ([record](docs/demo/piano/README.md), [comparison](docs/demo/piano/comparison.md)) |
| Full orchestrator flow on Linux (2026-09-29) | ✅ once with Claude workers (0.4.0, headless main session, no fix round); an independent check found tests failing on Node 18 and repeated notes not visibly re-struck ([record](docs/demo/piano/linux-run/README.md)) |
| New runs on `gpt-6-luna`, `gpt-6-sol`, `gpt-6-astra`, `gpt-5.5` (low) | ✅ requested model/effort applied, `Status: DONE`, `Scope: ok` |
| `--resume` on the same thread with effort low → medium | ✅ same thread, second turn logged as `gpt-6-luna/medium` |
| Subdirectory `--cwd` with an out-of-scope file | ✅ `Scope: outside allowed: pkg/extra.txt` (scope only; the root ledger is not writable from there, so since v0.3.0 the brief must be inside `--cwd`) |
| Codex sandbox boundary (`codex sandbox`, 2026-09-28) | ✅ writes inside `--cwd` work; outside `--cwd` and `.git` are denied; `git commit` fails on `index.lock` |
| Codex sandbox boundary on Linux (`codex sandbox`, 2026-09-29) | ✅ writes inside `--cwd` work; `.git` and the home directory are denied; ⚠️ `/tmp` is writable; network is off by default, loopback included |
| Unknown model / unsupported effort (`gpt-6-luna` + `minimal`) | ✅ `Status: BLOCKED` with a one-line reason |
| `gpt-6-luna` + `ultra` | ✅ since v0.4.1 `Status: BLOCKED` before Codex runs, because the model cache lists only up to `max` (before, the API accepted it and the level actually applied was unknown) |
| `TaskStop` during a run | ✅ worker, Codex and the command Codex was running all stop |
| `--disable plugins` (2026-09-29, `gpt-6-luna` low) | ✅ `Status: DONE`; the session log has no Superpowers skill or ponytail hook text, which an earlier worker run on the same machine had; user skills outside plugins remain |
| All test files in `tests/` + piano example | ✅ CI on Ubuntu (Node 22 and 18), macOS and Windows; the first run caught a macOS-only `realpath -m` bug, now fixed |
| `claude plugin validate .`, Codex `validate_plugin.py` | ✅ |

Limits: the orchestrator is a set of rules the host model follows, not an enforcement layer; the
scope check around a Claude worker runs only when the main session calls `scope-check.mjs`. Claude
workers use the `sonnet` alias, so they follow new Sonnet releases; change Codex model names in your
routing config. Live Codex progress is not streamed into the TUI by design.

## Development

```bash
python3 tests/test_codex_worker.py
python3 tests/test_scope_check.py
python3 tests/test_task_brief.py
python3 tests/test_sdd_safety.py
python3 tests/test_worktree_cleanup.py
python3 tests/test_worktree_instructions.py
python3 tests/test_brainstorm_companion.py
python3 tests/test_skill_text.py
python3 tests/test_release_manifests.py
python3 tests/test_find_polluter.py
(cd examples/piano && node --test)
claude plugin validate .
```

Issues and PRs: <https://github.com/lsy041015/orchestra/issues>. Reports from real orchestrator use on
macOS/Linux are especially welcome.

## Credits and license

Based on [Superpowers](https://github.com/obra/superpowers) 6.4.1 by Jesse Vincent, under the
[MIT License](LICENSE) with the original copyright kept. The upstream README is in
[UPSTREAM_README.md](UPSTREAM_README.md). The banner melody is Beethoven's *Ode to Joy* (public domain).

---

<p align="center"><sub>LSY.KOR · <a href="https://github.com/lsy041015">More projects</a></sub></p>
