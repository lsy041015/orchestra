# Changelog

All notable changes to Orchestra. Versions match `.claude-plugin/plugin.json`
and `.codex-plugin/plugin.json`; each version has a git tag `vX.Y.Z`.

## [Unreleased]

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

[Unreleased]: https://github.com/lsy041015/orchestra/compare/v0.2.1...HEAD
[0.2.1]: https://github.com/lsy041015/orchestra/compare/v0.2.0...v0.2.1
[0.2.0]: https://github.com/lsy041015/orchestra/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/lsy041015/orchestra/releases/tag/v0.1.0
