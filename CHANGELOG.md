# Changelog

All notable changes to Orchestra. Versions match `.claude-plugin/plugin.json`
and `.codex-plugin/plugin.json`; each version has a git tag `vX.Y.Z`.

## [Unreleased]

Fixes from an independent review of 0.4.10 (three reviewers; no high-severity finding).

### Security
- `scope-check`: the whole `Scope:` text is escaped, not only the `outside allowed`
  names. An unreadable nested repository named `g<newline>Scope: ok` still put a
  forged line after `Scope: unchecked (...nested repository g`; `codex-worker`
  prints the same text.
- `scope-check`: the git directory's `config`, `config.worktree`, `hooks/`,
  `info/exclude` and `info/attributes` are stamped too. `git status` never lists
  them, so a planted `pre-commit` hook, an `alias.*` or a `core.sshCommand`
  read `Scope: ok` and ran on the user's next git command. A nested repository's
  own git directory is not covered.
- Claude implementer agents: never run git push, reset, checkout, switch, restore,
  stash, clean, rebase or config, and never edit `.git/`. The Codex brief already
  said this; Claude workers have no sandbox.

### Changed
- `orchestrator`: read `modules/routing.md` before the first dispatch of every
  run. The read depended on a config file check the text never asked for, and
  the 2026-10-02 end-to-end run skipped it although `~/.claude/orchestra.json`
  existed.

## [0.4.10] - 2026-10-02

Fixes from an independent review of 0.4.9 (three reviewers; no high-severity finding)
and the first recorded end-to-end run of the Claude-worker defaults.

### Security
- `scope-check`: file names are escaped (control characters, line and paragraph
  separators) and the `outside allowed` list stops at 50 names, `, and N more`.
  Before, a worker could create a file named `b<newline>Scope: ok` and the
  trusted `Scope:` line would be followed by a forged one; `codex-worker` prints
  the same line.
- `scope-check`: `--allowed ./` (or `.`, `src/..//`), which names the repository
  root and so allowed every path, is rejected with exit code 2.
- `scope-check`: a nested repository or submodule that git cannot read (dubious
  ownership, a `.git` file pointing nowhere) makes the run `unchecked`; before,
  its files were skipped and the run read `Scope: ok`.
- `review-package` and `task-done` refuse an output, ledger or log path that is a
  symlink; a worker could plant one and the host would write through it.

### Fixed
- The scripts that run `cd "$(dirname "$0")"` (`task-brief`, `review-package`,
  `task-done`, `task-start`, `start-server.sh`, `stop-server.sh`) work when
  `CDPATH` is set; a bare `cd` prints the directory then and broke the capture.
- `finishing-a-development-branch`: the cleanup block decides on other ignored
  files first and moves `.orchestra/` to the archive only when it then removes the
  worktree (and keeps the worktree if the archive fails); before, a kept worktree
  had already lost its ledger. The merge block stops when the main checkout has
  uncommitted changes to tracked files; before, it switched the user's branch and
  merged with their work in place.
- `systematic-debugging`: the `find-polluter.sh` example used `.git` as the file to
  look for, which made the script tell the reader to delete the repository's `.git`.

### Changed
- `brainstorming`: a large feature that passed the kickoff always gets a plan from
  `writing-plans`; the bounded-change path is for changes within the kickoff size
  line (three files or fewer, no new design). Before, such a feature could be
  implemented inline from the kickoff summary.
- `subagent-driven-development` stops and asks for `git init` when the repository
  root is the home directory (before, only the Codex module said so, and a
  Claude-only run left its ledger in `~/.orchestra/`). `dispatch-claude.md` now
  holds the `--allowed` rules itself, so a Claude-only run no longer reads the Codex
  module, and it names `node` and `git` as requirements and tells the reader to add
  `__pycache__/`-style cache rules to `.git/info/exclude` before the first baseline.
- `scripts/` paths in `subagent-driven-development`, `executing-plans` and
  `visual-companion`, and the `find-polluter.sh` call, say they are relative to the
  skill's base directory. `writing-plans` says when to choose `executing-plans`.
- READMEs: Node.js is needed for every worker's scope check, three implementer
  agents, the three-fix-round limit, the ignored-folders limit, `--strict` in the
  validate command, a routing example that does not assume Codex, and the 300-line
  rule covers `skills/` and `agents/`.

### Verified
- The Claude-worker defaults ran end to end for the first time, on 0.4.9: Easy
  `orchestra:implementer-medium`, Medium `orchestra:implementer`, Hard
  `orchestra:implementer-xhigh`, plus one fix round through `SendMessage`. Each
  worker's transcript shows `claude-sonnet-5-5` at its tier's effort on every turn,
  so `sonnet` accepts `xhigh` and nothing was substituted. This replaces the 0.4.6
  note that `implementer-xhigh` had not been dispatched in a real run. Record,
  plan and ledger: `docs/orchestra/runs/2026-10-02-claude-worker-e2e/`.

## [0.4.9] - 2026-10-01

Fixes from a second review of 0.4.8: the scope check took git's word for what
changed, and the orchestrator never said to load the workflow it extends.

### Security
- `scope-check`: the top-level `git status` runs with `--ignore-submodules=all`,
  and every submodule is listed from the index and hashed with `git ls-files`.
  Before, status looked inside each submodule, so it ran that submodule's
  `filter.<x>.clean` driver, and a `submodule.<x>.ignore` or
  `diff.ignoreSubmodules` setting hid edits and commits there (`Scope: ok`).
  The 0.4.8 claim that submodules were covered held only for this first part.
- `scope-check`: files flagged assume-unchanged or skip-worktree are hashed on
  every run; `git update-index` hid any edit from `git status` before. A
  submodule's `.git` file is hashed too, so repointing it shows up.
- `codex-worker`: a line in Codex's reply that looks like the worker's own
  `Codex thread:` or `Scope:` line is quoted with `> `. Before, a reply holding
  `Scope: ok` came before the real `Scope: outside allowed: ...` line.

### Fixed
- `scope-check`: one edit in a clean submodule flags only that file, not every
  file in the submodule; a rewrite of a file directly inside an ignored
  directory counts (only additions and removals did), as `review-loop` already
  said; `--allowed sub/` also covers the submodule entry `sub`.
- Skills: `orchestrator` says to load `subagent-driven-development` for setup,
  the ledger, briefs, review and the final review, and `file-map` no longer
  sends that skill only to untiered work. `writing-plans` hands delegated work
  to the orchestrator in Claude Code instead of offering it next to SDD.
- Skills: one Codex opt-in rule. Named tiers go to Codex; "use Codex" with no
  tier uses the config's codex tiers.
- Skills: the fix loop also stops after three fix rounds on one task, not only
  after two failed fixes with one root cause. The rule is worded the same in
  all 13 files, and a test keeps it and the fix-route note identical.

## [0.4.8] - 2026-10-01

Fixes from a review of 0.4.7: the scope check could still run a command from a
nested repository, and the Codex timeout could wait on a process it never killed.

### Security
- `scope-check`: nested repositories and submodules are listed with `git ls-files`
  instead of `git status`. 0.4.7 switched off `core.fsmonitor` and hooks, but
  `git status` still ran a `filter.<x>.clean` or `process` driver from a
  worker-written `.git/config` and `.gitattributes` when a file's mtime moved, so
  the 0.4.7 note that this hole was closed was wrong.
- `review-package`: `--no-textconv`, so a textconv driver never runs.

### Fixed
- `codex-worker`: a timeout or a stop signal kills the whole Codex process tree
  five seconds after the polite signal (`taskkill /t` on Windows) and closes the
  pipes. Before, SIGKILL reached only the `codex` shim; a native binary that
  ignored SIGTERM kept running and the worker waited for it. A stopped worker now
  prints its BLOCKED report and `Scope:` line instead of exiting after 5 s.
- `codex-worker`: the default timeout is 110 min, inside the 2 h Bash background
  limit that killed the worker first, and `ORCHESTRA_CODEX_TIMEOUT_MS` is clamped
  to setTimeout's maximum.
- `scope-check`: ignored entries are labelled, e.g. `build/ (ignored)`;
  `review-loop` says which are expected (caches the brief's commands create) and
  no longer claims ignored paths are invisible.
- `brainstorm`: JSON error lines also escape line breaks and tabs.
- Skills: the process check is `ps -eo pid,args | grep -F` again (`pgrep -a`
  lists ancestors on macOS); the kickoff "large feature" test no longer reads as
  "no spec"; both dispatch modules use one script placeholder.
- Tests run under `pytest` too, and the Windows command-lookup test passes
  `FAKE_OUT` again (Windows CI was red from 0.4.7 on).

## [0.4.7] - 2026-10-01

Fixes from a review of 0.4.6: one command-execution hole in the scope check, a
blind spot for ignored files, and smaller script and wording fixes (#15, #16).

### Security
- `scope-check`: git runs with `core.fsmonitor`, `core.hooksPath` and
  `core.untrackedCache` off, so a nested repository a worker created can no longer
  run a command on the host through its `.git/config`.
- `review-package`: refs that start with `-` are refused, and `diff.external` never runs.
- `brainstorm`: `start-server.sh` refuses a symlinked `.orchestra`; the logged event
  `source` is set by the server, not the client.

### Fixed
- `scope-check` counts gitignored files (`.env`, `dist/`); `.orchestra/` stays excluded.
  A worker that writes an ignored file now shows as `outside allowed`.
- `task-brief`: a same-level section (`### Verification`) ends the task instead of
  joining its brief.
- `codex-worker`: `ORCHESTRA_CODEX_TIMEOUT_MS` (default 2 h) stops a hung Codex and
  reports BLOCKED; output memory is bounded; a signal arms a 5 s exit.
- `brainstorm`: fragmented WebSocket frames are refused; JSON error lines are escaped.
- `sdd-workspace`: the plan marker is claimed atomically.
- Skills: `file-map` reads `routing.md` only when a config file exists or Codex is
  named; the kickoff gate has a two-round cap and a proceed exit; "approved plan"
  accepts kickoff approval; `using-orchestra` has a narrower trigger; the ledger
  `Routing:` line includes UI; `review-loop` uses `pgrep`.

### Not changed
- Windows `codex.cmd` lookup, the brainstorm owner-PID heuristic and the duplicated
  worker preset text were left for later.

## [0.4.6] - 2026-10-01

Kickoff questions, Claude workers by default, and modular skills that load only
the file a situation needs.

### Added
- `using-orchestra/references/file-map.md`: which file to read in which situation, so
  an agent opens one file instead of a whole skill. A test requires it to name every
  `SKILL.md` and module and every path it lists to exist.
- Tests: every markdown file under `skills/` and `agents/` is at most 300 lines; the
  kickoff gate, the Claude default routing and the force-push guard keep their text.

### Changed
- `brainstorming`: a new project, or a large feature with no spec or plan, starts with
  one kickoff gate: ask until the deliverable, success criteria, constraints and
  non-goals are clear, summarize them back and get approval. After it, questions
  stay limited to missing information and consequential decisions.
- `writing-plans` runs `brainstorming` first when no kickoff or design was approved;
  `orchestrator` takes the kickoff approval as the plan's authorization instead of
  an "approved plan" nothing approved.
- `orchestrator` dispatches Claude workers by default, with no question: Easy
  `claude sonnet/medium`, Medium `claude sonnet/high`, Hard and UI
  `claude sonnet/xhigh`. A Codex worker is used only when the user named Codex in the
  conversation; a `codex` value in `orchestra.json` stays inert until then, and Codex is
  never offered in a question unprompted. `routing.md` and the Codex dispatch module are
  read only when a config file exists or Codex was named. The default Hard and UI tier
  uses `orchestra:implementer-xhigh`, which has not yet been dispatched in a real run.
- `orchestrator`, `finishing-a-development-branch` and `using-git-worktrees` keep
  the always-needed steps in `SKILL.md` and move situational text, verbatim, to
  `modules/`: routing, Claude and Codex dispatch and review loop; merge, discard and
  cleanup; the git worktree fallback. `SKILL.md` says when to read each. Fewer
  bytes load when a path is not taken (a PR finish drops 4.7 KB of 9.1 KB, a native
  worktree 4.0 KB of 8.4 KB); a run that takes every path loads 5 to 14% more, the
  pointers.
- `writing-skills/anthropic-best-practices.md` (1,160 lines) is split into six parts
  under `writing-skills/best-practices/`, content unchanged.
- `test_worktree_cleanup.py` and `test_worktree_instructions.py` read the shell blocks
  from the modules.

### Removed
- `Quick Reference` and `Common Rationalizations` sections from
  `finishing-a-development-branch`, `using-git-worktrees` and `systematic-debugging`
  (5 KB): every row restated a rule the skill body already gives. The one rule only
  the table held, no force-push after a rejected push, moved into the Option 2 text.

## [0.4.5] - 2026-10-01

### Added
- `orchestra:implementer-xhigh` Claude agent (same contract, `sonnet` / `xhigh`), so a
  routing value such as `claude sonnet/xhigh` has an agent to dispatch. The
  orchestrator's effort table lists it.

### Fixed
- `scope-check.mjs`: each snapshot read and hashed every untracked file, so a
  checkout with large untracked trees (a repository at `~`: 950k files,
  145 GB) never finished, which stalled both Claude dispatch and every Codex
  run. Files are now compared by size and change times.
- A repository root at or above the home directory lists every app cache as
  untracked: the scope check now prints `unchecked` there at once, and
  `codex-worker.mjs` refuses such a `--cwd`, where the sandbox could write
  `~/.ssh` and shell profiles. The orchestrator asks for a project `git init`.
- `subagent-driven-development`: a ledger outside Git could land in a session
  scratchpad and was gone after a resume; it must outlive the session.
- `writing-plans`: a plan's test command had never been run, and the runner
  rejected its invocation in every task. Each new command now runs once
  before it goes into the plan.

## [0.4.4] - 2026-09-30

Fixes from a four-part review of the installed 0.4.3 (scripts, skill rules,
diagnosis and companion safety, packaging). Each fix has a regression test
that fails on 0.4.3.

### Fixed
- `scope-check.mjs`: a staged rename recorded only its new path, so moving an
  out-of-scope file into an allowed name printed `Scope: ok`. Edits inside an
  untracked nested repository (a colcon `src/` checkout, say) or an already
  dirty submodule hashed as `EISDIR` before and after and were never seen.
  Both are now counted, commits inside a nested repository included.
- `executing-plans`: `task-done` marked a task `complete` before the inline
  review, so a compaction in between skipped the review for good. It now
  runs after the review is clean, after the last fix.
- `orchestrator`: a Claude worker reused for a later task had no scope
  baseline, and `scope-check after` failed or counted the earlier task. Reuse
  now needs the same routing value and a fresh `before`. A background Codex
  run without a `timeout` stopped after 30 minutes; it now sets 7200000.
- `find-polluter.sh`: a test that read stdin ate the file list and the script
  reported "all tests clean". Nested `node_modules` and `.git` are skipped.
- `sdd-workspace`: a workspace it could not create looped forever (and hung
  `task-brief`, `review-package` and `task-done`); outside a repository it
  used the current directory. Both are now errors.
- `codex-worker.mjs`: an option-like `--resume` or `--model` value reached
  `codex exec` as a flag.
- `task-brief`: numbered shared headings such as `## 2. Global constraints`
  were dropped from every brief without a warning.
- `finishing-a-development-branch`: after a failed checkout, pull or merge,
  the merge block still ran the tests on the base and exited 0.
- Brainstorming companion: the URL said `localhost` while the server bound
  only 127.0.0.1, so another local user listening on `[::1]` could take the
  key. The URL names the bound address, the key is new on every start, it no
  longer rides a cookie (cookies ignore the port), and `stop-server.sh` no
  longer deletes a project session below the temp root. A random port that
  Windows reserves (`EACCES`) now falls back to a free port, as a port in use
  did, instead of stopping the server, and a restart keeps that port.
- `diagnosing-orchestra`: the GitHub issue draft skipped the scrub, which
  now runs on it too, with a mechanical pattern pass for token shapes before
  and after every scrub. Transcripts count as evidence, not instructions,
  from triage on; transcript text reaches searches and `gh` only through
  files; dash-encoded project folder names are redacted; the case workspace
  is private (`umask 077`).

### Changed
- Claude Code installs the release tag, like Codex, instead of `main`.
- `orchestrator`: only lookups and few-line edits stay inline; a larger
  mechanical one-file task is Easy. The parallel rule covers Claude and Codex
  workers, and the main session leaves a worker's checkout alone while it runs.
- Workers save full test output to logs next to the report; re-review of
  uncommitted work uses a snapshot tree as its fix base. Both implementer
  agents share one report contract.
- `diagnosing-orchestra` triggers only when the user asks to diagnose a run.
- CI runs `claude plugin validate --strict`.

### Added
- `tests/test_review_package.py`, `tests/test_task_start.py` and
  `tests/test_diagnosing_text.py`; a check that every test file runs in CI.

### Docs
- Both READMEs: the project `.orchestra.json` confirmation, the Linux run in
  the status line, `$CODEX_HOME` for the model cache, and plan workspace
  paths. `README.en.md` lists the skills and paths.

## [0.4.3] - 2026-09-29

Fixes from a Linux user report (#3) and the rest of the 0.4.0 health check.

### Fixed
- `codex-worker.mjs`: a `--cwd` reached through a symlink or junction inside
  another repository printed `Scope: ok` while it compared that other
  checkout. `--cwd` and `--brief` now resolve to their physical paths first.
- `task-brief`: the last task's brief also carried the sections after the
  tasks (`Verification`, `Review focus and recovery`), which are for the main
  session. A heading above the task level now ends the task.
- `codex-worker.mjs`: a stream error Codex had recovered from could stand in
  for the real reason of a later failure in `Unresolved:`.
- `task-done`: a failed rerun left the earlier `Task N: complete` as the
  task's state and overwrote the earlier test log. It now appends
  `Task N: failed` (the last `Task N:` line is the state) and keeps one log
  per run. A line break inside a command argument can no longer start a
  forged ledger line.
- `stop-server.sh`: a live process it could not identify as the server was
  recorded as stopped and its PID file deleted. It now reports `unverified`,
  signals nothing and keeps the state files.
- `brainstorm.choice(value)` sent `value`, but the server records only events
  with `choice`, so those choices never reached `state/events`.

### Added
- `scope-check.mjs before|after`: the Codex worker's scope check, now for
  Claude workers too. The main session records a baseline before dispatch and
  checks it before each review. The check also counts files a worker
  committed, which leave `git status` clean.
- Every task brief includes the plan's `Global constraints` and `Interfaces`
  sections, which bind every task.

### Changed
- Codex workers run with `--disable plugins`, so the user's Codex plugins
  (another Superpowers, for one) no longer add their skills and hooks to a
  worker. `config.toml` and `AGENTS.md` still apply.
- `orchestrator`: a Claude worker reused through `SendMessage` keeps its
  first task label; the ledger shows its current task.
- README: running the scripts from PowerShell on Windows.

### Removed
- The inactive Antigravity, Gemini, Hermes, Muse and Pi tool notes under
  `using-orchestra/references/`.

## [0.4.2] - 2026-09-29

The rest of a pre-0.4.0 review, ported from a branch that was never pushed.

### Fixed
- `codex-worker.mjs`: a SIGINT, SIGTERM or SIGHUP sent to the worker now
  reaches Codex, so stopping only the worker no longer leaves Codex editing
  files (POSIX; on Windows, TaskStop already ends the whole process tree).
- `task-done`: a task number with a newline could append a forged
  `Task N: complete` line to the ledger. It is now rejected, as in
  `task-brief`, and both executing-plans helpers run through bash.
- `find-polluter.sh`: it said "all tests clean" when the pollution already
  existed or when there was no npm test script, and it split file names at
  spaces. Those cases now stop with an error, and each name stays whole.
- `diagnosing-orchestra` no longer depends on context-mode, which Orchestra
  does not ship; long transcripts go through `references/context-safety.md`.

### Changed
- `orchestrator`: routing from a project `.orchestra.json` needs one
  confirmation per project before the first dispatch, because a cloned
  repository can ship values that spend the user's quota.
- `diagnosing-orchestra` shows the search terms and asks before searching
  GitHub, since they leave the machine.
- Review skills allow a worker model switch the user asks for;
  `systematic-debugging` tells implementation workers to return
  `Status: BLOCKED` with the evidence instead of retrying.
- The Codex marketplace installs the release tag instead of `main`.

### Added
- `tests/test_release_manifests.py` keeps the manifests, the Codex
  marketplace ref, this changelog and the READMEs on one version.
- `tests/test_find_polluter.py`. Both new test files run in CI, and a CI job
  runs `claude plugin validate`.

### Docs
- Both READMEs end with the shared profile footer, and LICENSE credits the
  Orchestra changes.

## [0.4.1] - 2026-09-29

Fixes from a health check of the installed 0.4.0 by Claude and a Codex review
(gpt-6-astra, effort max). Every regression test added here fails on 0.4.0.

### Fixed
- `finishing-a-development-branch`: cleanup read shell variables set in an
  earlier tool call, and Claude Code starts each call in a fresh shell, so
  removal was silently skipped. It now takes the recorded worktree path. The
  merge step finds the main worktree with `git worktree list`, so a bare
  repository no longer merges inside the feature worktree.
- Worktree cleanup no longer deletes ignored files. `git worktree remove`
  deleted them without a word, Orchestra's own ledger and reports included.
  `.orchestra/` now moves to `<main checkout>/.orchestra/archive/<worktree>-<time>/`
  first; any other ignored file (such as `.env`) stops the removal and is shown.
- `using-git-worktrees`: a `D:/`-style location counts as absolute, Python
  requirements install only into an active virtualenv, and a `.gitignore`
  change is reported.
- Brainstorming companion: a trailing option without a value no longer loops
  forever; a relative `--project-dir` no longer puts session state in the
  plugin's folder; temp sessions come from `mktemp` and are removed on stop;
  `$&`, `$'` and `$$` in screens stay literal; `/files/` names are URL-decoded;
  a vanished file answers 500 instead of crashing the server; the WebSocket
  also works behind HTTPS tunnels.
- `codex-worker.mjs`: when Codex's model cache lists a model without the
  requested effort (for example `gpt-6-luna` + `ultra`, which the API accepted
  without saying which level ran), the worker returns `Status: BLOCKED` before
  Codex runs.

### Docs
- Run C of the piano demo (`docs/demo/piano/linux-run/`): the same plan on
  Linux with 0.4.0, Claude workers and a headless main session. It finished
  with no fix round in 7 min 2 s of worker time. An independent check found
  the two issues runs A and B had fixed: the tests fail on Node 18 because
  there is no `package.json`, and a repeated note's second strike is not
  visible.

## [0.4.0] - 2026-09-29

A cleanup release after a repository review. The renames are breaking.

### Changed
- **Breaking:** `using-superpowers` and `diagnosing-superpowers` are now
  `using-orchestra` and `diagnosing-orchestra`. Working directories and
  default paths move with them: `.superpowers/sdd/` to `.orchestra/sdd/`,
  `.superpowers/brainstorm/` to `.orchestra/brainstorm/`,
  `~/.superpowers/diagnosing-superpowers/` to
  `~/.orchestra/diagnosing-orchestra/`, and `docs/superpowers/plans/` and
  `specs/` to `docs/orchestra/`. To resume an unfinished run, move
  `.superpowers/sdd/<plan>/` to `.orchestra/sdd/<plan>/`. Plans saved under
  `docs/superpowers/` still work when their path is given.
- `writing-plans`: a plan records decisions, not code. A task is ready when
  the worker can write exactly one reasonable thing from it, and the
  self-review checks the plan's length against the spec. Ported from
  Superpowers 6.4.2 (obra/superpowers#2333).

### Fixed
- `brainstorming` links the visual companion guide for when the user asks
  for the browser companion. No skill linked it, so the companion could not
  be started.

### Added
- `tests/test_skill_text.py`, also in CI: every `orchestra:<name>` reference
  and relative link in the READMEs, agents, skills and docs resolves, and
  the host implementer preset is the same in every skill and matches
  `agents/implementer.md`.

### Removed
- 12 files no skill links to (1,172 lines): the plan and spec
  document-reviewer prompts, which also contradicted the no-reviewer rule;
  the systematic-debugging pressure tests and creation log; and the
  writing-skills persuasion, subagent-testing, graphviz and CLAUDE.md
  testing material.

### Docs
- Both READMEs record the Linux sandbox boundary (Codex 0.156.1): `.git`
  and the home directory are denied, `/tmp` is writable.
- The English README also warns against enabling the earlier `relay`
  plugin alongside Orchestra.

## [0.3.1] - 2026-09-29

### Added
- `codex-worker.mjs`: `ORCHESTRA_CODEX_NETWORK=1` adds
  `-c sandbox_workspace_write.network_access=true`. The `workspace-write`
  sandbox blocks every socket, loopback included, so ROS 2/DDS tests,
  localhost servers and package installs failed inside a Codex worker.
  Network stays off by default; the orchestrator sets it only for tasks
  that need it and records `Network: on` in the ledger. Verified on Linux
  with Codex 0.156.1 (`codex sandbox`: `PermissionError` without the flag,
  a loopback UDP send with it).

### Docs
- The Korean README no longer says the `sonnet` alias is Sonnet 5. The alias
  follows new Sonnet releases, as the English README already said.

## [0.3.0] - 2026-09-28

Fixes from a pre-release review. Each item below was reproduced before the fix.

### Fixed
- `codex-worker.mjs`: when `git status` failed after the run, the scope check
  printed `Scope: ok`. Any git failure (not a repository, dubious ownership,
  a failure after the run) is now `Scope: unchecked (<reason>)`.
- `codex-worker.mjs`: outside Claude Code on Windows, a `codex.cmd` or
  `git.exe` inside the project ran instead of the real tool. The worker now
  sets `NoDefaultCurrentDirectoryInExePath`.
- `codex-worker.mjs`: an `error` event for a stream retry that Codex recovered
  from made the run `BLOCKED`. A reply with no `Status:` line now does.
- `using-git-worktrees`: after a failed `git worktree add`, the steps still
  marked the existing directory as Orchestra-owned, so cleanup could delete
  someone else's worktree. The steps now stop at the first failure. The path
  variable is no longer named `path`, which zsh ties to `PATH`.
- `finishing-a-development-branch`: after a failed checkout of the base branch,
  the feature was merged into the current branch. The steps now stop at the
  first failure, and `git pull --ff-only` runs only when there is an upstream.
  `git worktree prune` is gone (it also dropped other worktrees). A new check
  before the menu catches reviewed work that is not committed.
- `sdd-workspace`: Git Bash wrote the plan marker as an absolute path. It is
  repo-relative again, and old absolute markers still resolve.
- Brainstorming companion: every page loaded a logo from primeradiant.com and
  said "Superpowers". Pages now load nothing remote. Session files under
  `.superpowers/brainstorm/`, including the saved key, are git-ignored.

### Changed
- Codex workers need the brief inside `--cwd`, normally the repository root,
  because the sandbox writes only there. They never commit, since the sandbox
  keeps `.git` read-only; the main session commits after review.
- The READMEs no longer claim that subagents are structurally blocked for
  Codex workers. Codex 0.156 keeps its agent tools even with
  `features.multi_agent=false`, so for Codex this remains a brief rule.
- Claude agents use the `sonnet` alias instead of `claude-sonnet-5`.
  `orchestra:implementer` reports are capped at 40 lines (20 per fix), as the
  medium agent's already were.
- When `orchestra:orchestrator` is active, the other skills now defer to it
  for worker choice, parallel runs and the fix loop. `writing-plans` offers
  the orchestrator after a plan.
- `using-git-worktrees` uses Claude Code's `EnterWorktree` only when the user
  explicitly asks for a worktree.
- Diagnosis prompts and templates say Orchestra instead of Superpowers.
- The README banner and the Codex plugin icons carry no third-party logos.
  Unused upstream logo files are removed.
- The code of conduct is Orchestra's own. Reports go to this project's
  maintainer, not to Prime Radiant.
- `.gitattributes` keeps LF line endings on every platform.

### Added
- Regression tests for each fix above, including
  `tests/test_brainstorm_companion.py`, which also runs in CI.

### Docs
- Update instructions now use `claude plugin update orchestra@orchestra`;
  `plugin install` does not upgrade an existing install.
- `docs/demo/piano/comparison.md`: the same plan rebuilt with Claude workers
  only, compared with the Codex-worker run (time, fix rounds, findings, tokens).

## [0.2.1] - 2026-09-28

### Fixed
- `using-git-worktrees`: the worktree safety check used GNU-only `realpath -m`
  and failed on macOS. A portable `resolve_path` now resolves the existing part
  of the path with `pwd -P` and keeps the missing tail.
- Tests find `bash` through `PATH`, so Windows machines with WSL no longer pick
  `System32\bash.exe` instead of Git Bash.
- `examples/piano/README.md`: the test command now works on Node.js 18 and 20.

### Added
- GitHub Actions CI on every push and pull request: Ubuntu (Node 22 and 18),
  macOS and Windows, covering all tests in `tests/` and the piano example.
- First recorded end-to-end orchestrator run: `examples/piano/` (a one-octave
  web piano) and `docs/demo/piano/` with the ledger, GIF, screenshots, review
  findings and Codex token usage.
- CI badge in both READMEs.

## [0.2.0] - 2026-09-27

### Fixed
- `codex-worker.mjs`: the scope check now resolves `--allowed` against the
  repository root, so a subdirectory `--cwd` no longer flags allowed files or
  misses edits to files that were already dirty.
- `task-brief` keeps CRLF bytes under Git Bash `gawk` (`BINMODE=3`).
- The full test suite passes on Windows (UTF-8 I/O, path spelling, symlink
  skip without symlink rights).

### Added
- `codex-worker.mjs`: `--allowed` entries ending in `/` allow a whole
  directory; the `ultra` effort; Codex API rejections (unknown model,
  unsupported effort) reduced to one readable line.
- Orchestrator skill: rule for Scope lines from parallel workers, gitignored
  path limitation, a concrete stray-process check, `codex login status`
  preflight, and never switching models silently on errors. Codex no longer
  invokes the Claude Code-only orchestrator implicitly.
- README banner, `README.en.md`, and a real Codex CLI verification table
  (four models, resume with effort change, error paths, cancellation).

### Changed
- Codex plugin manifest text rewritten for Orchestra.

## [0.1.0] - 2026-09-27

### Added
- First Orchestra release, renamed from the author's `relay` fork of
  [Superpowers](https://github.com/obra/superpowers) 6.4.1.
- `orchestra:orchestrator`: difficulty-tiered task table, per-tier routing to
  Claude subagents or Codex CLI workers (`~/.claude/orchestra.json`,
  `<project>/.orchestra.json`), task-list labels, and a fix loop.
- `codex-worker.mjs`: runs `codex exec` directly with validated arguments,
  thread resume, and a before/after scope check.
- `orchestra:implementer` and `orchestra:implementer-medium` Claude agents.

[Unreleased]: https://github.com/lsy041015/orchestra/compare/v0.4.8...HEAD
[0.4.8]: https://github.com/lsy041015/orchestra/compare/v0.4.7...v0.4.8
[0.4.7]: https://github.com/lsy041015/orchestra/compare/v0.4.6...v0.4.7
[0.4.6]: https://github.com/lsy041015/orchestra/compare/v0.4.5...v0.4.6
[0.4.5]: https://github.com/lsy041015/orchestra/compare/v0.4.4...v0.4.5
[0.4.4]: https://github.com/lsy041015/orchestra/compare/v0.4.3...v0.4.4
[0.4.3]: https://github.com/lsy041015/orchestra/compare/v0.4.2...v0.4.3
[0.4.2]: https://github.com/lsy041015/orchestra/compare/v0.4.1...v0.4.2
[0.4.1]: https://github.com/lsy041015/orchestra/compare/v0.4.0...v0.4.1
[0.4.0]: https://github.com/lsy041015/orchestra/compare/v0.3.1...v0.4.0
[0.3.1]: https://github.com/lsy041015/orchestra/compare/v0.3.0...v0.3.1
[0.3.0]: https://github.com/lsy041015/orchestra/compare/v0.2.1...v0.3.0
[0.2.1]: https://github.com/lsy041015/orchestra/compare/v0.2.0...v0.2.1
[0.2.0]: https://github.com/lsy041015/orchestra/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/lsy041015/orchestra/releases/tag/v0.1.0
