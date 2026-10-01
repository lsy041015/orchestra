# Review and fix loop

Part of `orchestra:orchestrator`. Read it when a worker result is ready to review.


Review every result from the actual diff. After each worker run, read its
`Scope:` line (Codex worker output, or `scope-check.mjs after` for Claude):
- Treat `Scope: outside allowed` as a review finding (see the parallel rule
  in `SKILL.md` §3). An entry marked `(ignored)` is a `.gitignore`d path:
  caches and build output that the brief's own commands create
  (`__pycache__/`, `.pytest_cache/`, `node_modules/`, `build/`) are expected;
  any other ignored file (`.env`, a key, a local config) is a finding. Only an
  ignored directory's direct entries are compared, so review deeper edits
  there from the diff and the worker report.
- `Scope: unchecked (<reason>)` means no mechanical check ran: not a git
  repository, git refused it (for example dubious ownership), or git failed
  after the run. Review `git status` and the whole diff yourself, and tell the
  user why the check was skipped.
- Codex workers never commit. When the plan asks for commits, the main session
  commits each task after its review is clean.
- Check for processes left running from the project directory: on Windows,
  `Get-CimInstance Win32_Process | Where-Object CommandLine -like '*<project>*'`;
  elsewhere, `ps -eo pid,args | grep -F "<project>"` (the grep line itself is
  listed; ignore it). `pgrep -a` lists ancestors on macOS. Ask before stopping a
  process the user may own.

For a Claude worker, send findings to that worker with `SendMessage`. For a
Codex worker, write the follow-up fix described at the end of
`implementer-prompt.md` (each finding with file and location, required
behavior, covering tests, the report instruction) plus the Codex rules to
`<workspace>/task-N-codex-fix-K.md`, then rerun the worker with the same
`--model`, `--effort`, `--cwd` and `--allowed`, plus `--resume <thread>` and
that fix brief. A reply without a status block comes back as
`Status: BLOCKED` (`Codex reply has no status block`); resume the thread with
the missing answer. At the fix-round limit (two failed fixes with the same root cause, or three fix rounds on one task), the main session writes a `Ruling:` and
replans or fixes inline.
