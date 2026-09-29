# Changelog

All notable changes to Orchestra. Versions match `.claude-plugin/plugin.json`
and `.codex-plugin/plugin.json`; each version has a git tag `vX.Y.Z`.

## [Unreleased]

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

[Unreleased]: https://github.com/lsy041015/orchestra/compare/v0.3.0...HEAD
[0.3.0]: https://github.com/lsy041015/orchestra/compare/v0.2.1...v0.3.0
[0.2.1]: https://github.com/lsy041015/orchestra/compare/v0.2.0...v0.2.1
[0.2.0]: https://github.com/lsy041015/orchestra/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/lsy041015/orchestra/releases/tag/v0.1.0
