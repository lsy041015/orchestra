<p align="center">
  <img src="assets/orchestra-banner.png" alt="Orchestra — Claude × Codex" width="100%">
</p>

<p align="center"><a href="README.md">한국어</a> · <b>English</b></p>

<p align="center"><a href="https://github.com/lsy041015/orchestra/actions/workflows/tests.yml"><img src="https://github.com/lsy041015/orchestra/actions/workflows/tests.yml/badge.svg" alt="tests"></a></p>

# Orchestra

> **The conductor plans. The right model plays.**
> Your Claude Code main session plans and reviews; each bounded implementation task goes to a
> **Claude subagent** or a **Codex CLI (GPT)** worker picked per difficulty tier.

A personal fork of [Superpowers](https://github.com/obra/superpowers) 6.4.1 by Jesse Vincent.
Not an official OpenAI, Anthropic or Superpowers release. The Claude and Codex logos in the banner
only indicate the tools this plugin works with; the marks belong to their owners.

> **Status: experimental (v0.2.1).** See the [changelog](CHANGELOG.md). Used daily on Windows; tests run in CI on Ubuntu, macOS and
> Windows. Real orchestrator use on macOS/Linux is not recorded yet, and no usage savings are claimed. See [Verification and limits](#verification-and-limits).

## Why

If you pay for both Claude and ChatGPT (Codex), one quota tends to run out while the other goes unused,
and the most expensive model ends up doing mechanical edits. Orchestra keeps judgment in one place and
spends each subscription where it fits:

1. **The main session owns judgment.** Planning, review, diagnosis and integration never leave it, and
   the plugin never changes its model or reasoning effort.
2. **Workers only implement**, one bounded task each, inside an explicit list of allowed files.
3. **Every result is checked against evidence**: the real diff, real test output, and a mechanical
   scope check for Codex runs.

## How it works

```text
request → plan (orchestra:writing-plans)
        → tier table   | # | Task | Tier | Files |
        → routing      ~/.claude/orchestra.json + <project>/.orchestra.json, ask only for missing tiers
        → dispatch     Claude: Agent(orchestra:implementer, model=…)
                       Codex:  node codex-worker.mjs … (background Bash)
        → review       diff + tests + Scope line → fix loop (same worker / --resume <thread>)
        → ledger       Task N: complete → final verification → commit (push only after you confirm)
```

Tiers: **Easy** (mechanical, one file), **Medium** (normal feature or fix with tests), **Hard**
(cross-file or tricky logic), **Hard (UI)** (needs visual judgment). One-file edits stay inline.

Workers show up in the Claude Code task list with their engine, model and effort, e.g.
`[Codex gpt-6-luna/high] Task 3: retry helper`. Cancel one with `TaskStop`, or say
"switch Task 3 to claude opus".

## A real run

<p align="center"><img src="docs/demo/piano/piano-demo.gif" alt="A web piano built by Orchestra playing Ode to Joy" width="640"></p>

One unedited end-to-end run: a one-octave web piano ([`examples/piano/`](examples/piano/)) split
into three tasks and routed to three Codex workers (`gpt-6-luna/medium`, `gpt-6-sol/medium`,
`gpt-6-sol/high`), two of them in parallel, 13 min 28 s of worker time. Every worker reported
`DONE`, and main-session review still found five issues: a plan gap, a wrong verification command,
doubled key borders, a console error, and invisible repeated notes. Each task needed one
`--resume` fix round. Timeline, findings, browser checks and Codex token usage are in the
[run record](docs/demo/piano/README.md) (Korean). Claude workers were not part of this run.

## Install

Requirements: Claude Code, Git + Bash (Git Bash on Windows), Python 3 for the tests, and for Codex
workers Node.js 18+ and a logged-in Codex CLI (`codex --version`, `codex login status`).

```bash
claude plugin marketplace add lsy041015/orchestra
claude plugin install orchestra@orchestra
```

Start a new session afterwards. Update with `claude plugin marketplace update orchestra` followed by
the install command again.

Codex as the host (shared skills only; `orchestrator` is Claude Code only):

```bash
codex plugin marketplace add lsy041015/orchestra
codex plugin add orchestra@orchestra
```

Do not enable the original Superpowers plugin at the same time; skill names collide.

## Routing config

```json
{
  "routing": {
    "easy":   "codex gpt-6-luna/medium",
    "medium": "claude sonnet/high",
    "hard":   "claude opus/high",
    "ui":     "claude opus/high"
  },
  "options": ["codex gpt-6-luna/medium", "codex gpt-6-luna/high",
              "claude sonnet/high", "claude opus/high"]
}
```

- `~/.claude/orchestra.json` holds your defaults; `<project>/.orchestra.json` overrides them per key.
  A project `options` array replaces yours.
- Values are `<codex|claude> <model>/<effort>`.
  - Claude: an `Agent` model alias (`sonnet`, `opus`, `haiku`). Effort `high` →
    `orchestra:implementer`, `medium` → `orchestra:implementer-medium`.
  - Codex: any model your account can use. Effort is one of `none`, `minimal`, `low`, `medium`,
    `high`, `xhigh`, `max`, `ultra`. Support varies by model, and an unsupported pair comes back as
    `Status: BLOCKED` with Codex's own message.
- If every tier in the table has a value, Orchestra shows the mapping and starts. Otherwise it asks
  only for the missing tiers.

## Codex worker

```text
node skills/orchestrator/scripts/codex-worker.mjs \
  --model gpt-6-luna --effort high --cwd "<project>" \
  --brief "<ledger>/task-3-codex-prompt.md" \
  --allowed "src/retry.ts,test/retry.test.ts,test/fixtures/" [--resume <thread_id>]
```

- Runs `codex exec --json … -s workspace-write` directly and passes the brief on stdin. Paths never
  go through a shell, and every value that reaches the Windows shell is validated first.
- `--allowed` is relative to `--cwd`; an entry ending in `/` allows that whole directory. `--cwd` may
  be a subdirectory of the repository.
- Output: Codex's final message (the status block), then `Codex thread: <id>` and
  `Scope: ok | outside allowed: <repo-relative paths> | unchecked (not a git repo)`.
- Failures (non-zero exit, `turn.failed`/`error` event, no message) become `Status: BLOCKED` with a
  one-line reason and exit 1. Bad arguments exit 2 without starting Codex.
- The scope check hashes `git status` entries before and after the run, so files you had already
  modified are only flagged if Codex changes them. It cannot see `.gitignore`d paths, and parallel
  workers in the same checkout see each other's files; the orchestrator ignores only files that
  belong to another running worker's allowed list.

## Verification and limits

Checked on 2026-09-27, Windows 11, Codex CLI 0.156.1 (ChatGPT login). The model and effort that were
actually applied were read from Codex's session log (`turn_context`).

| Case | Result |
|---|---|
| Full orchestrator flow (plan → dispatch → review → fix → ledger) | ✅ once, [Orchestra Piano](docs/demo/piano/README.md); all tiers on Codex, no Claude worker |
| New runs on `gpt-6-luna`, `gpt-6-sol`, `gpt-6-astra`, `gpt-5.5` (low) | ✅ requested model/effort applied, `Status: DONE`, `Scope: ok` |
| `--resume` on the same thread with effort low → medium | ✅ same thread, second turn logged as `gpt-6-luna/medium` |
| Subdirectory `--cwd` with an out-of-scope file | ✅ `Scope: outside allowed: pkg/extra.txt` |
| Unknown model / unsupported effort (`gpt-6-luna` + `minimal`) | ✅ `Status: BLOCKED` with a one-line reason |
| `gpt-6-luna` + `ultra` | ⚠️ accepted by the API although the model list tops out at `max`; the level actually applied is unknown |
| `TaskStop` during a run | ✅ worker, Codex and the command Codex was running all stop |
| All five test files in `tests/` + piano example | ✅ CI on Ubuntu (Node 22 and 18), macOS and Windows; the first run caught a macOS-only `realpath -m` bug, now fixed |
| `claude plugin validate .`, Codex `validate_plugin.py` | ✅ |

Limits: the orchestrator is a set of rules the host model follows, not an enforcement layer. Model
names change over time, so update your config and the agent frontmatter. Live Codex progress is not
streamed into the TUI by design.

## Development

```bash
python3 tests/test_codex_worker.py
python3 tests/test_task_brief.py
python3 tests/test_sdd_safety.py
python3 tests/test_worktree_cleanup.py
python3 tests/test_worktree_instructions.py
(cd examples/piano && node --test)
claude plugin validate .
```

Issues and PRs: <https://github.com/lsy041015/orchestra/issues>. Reports from real orchestrator use on
macOS/Linux are especially welcome.

## Credits and license

Based on [Superpowers](https://github.com/obra/superpowers) 6.4.1 by Jesse Vincent, under the
[MIT License](LICENSE) with the original copyright kept. The upstream README is in
[UPSTREAM_README.md](UPSTREAM_README.md). The banner melody is Beethoven's *Ode to Joy* (public domain).
