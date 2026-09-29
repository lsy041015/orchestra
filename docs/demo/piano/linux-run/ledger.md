Plan: docs/superpowers/plans/2026-09-27-piano-demo-plan.md
Run: C (Linux, Orchestra 0.4.0), start commit 910ae7e, branch demo-run-c, headless (no questions)
Environment: Ubuntu Linux 6.8, Node v22.22.2, Python 3.10.12, /usr/bin/google-chrome
Workspace: .orchestra/sdd/2026-09-27-piano-demo-plan/ (self-ignored)

## Tasks

| # | Task | Tier | Files |
|---|------|------|-------|
| 1 | Note table and melody | Easy | examples/piano/notes.js, examples/piano/notes.test.mjs |
| 2 | Scheduler and Web Audio player | Medium | examples/piano/player.js, examples/piano/player.test.mjs |
| 3 | Piano page | Hard (UI) | examples/piano/index.html, examples/piano/style.css, examples/piano/app.js |

Routing: Easy=claude sonnet/medium, Medium=claude sonnet/high, Hard=claude opus/high, UI=claude opus/high
Routing source: project .orchestra.json (overrides ~/.claude/orchestra.json by key; every tier set, no questions)
Workers: Easy -> orchestra:implementer-medium (sonnet); Medium -> orchestra:implementer (sonnet); UI -> orchestra:implementer (opus)
Order: Tasks 1 and 2 in parallel (disjoint files, plan says independent); Task 3 after both are clean.
BASE for all tasks: 910ae7e (no commits in this run; review = working-tree diff)

## Rulings

Ruling 1 (Codex verification): routing contains no Codex tier, so no Codex run exists and
Verification 3 ("Scope: ok") is not applicable. Substitute: after each worker, main session
checks `git status --porcelain` shows only that task's listed files (plus earlier tasks' files).

Ruling 2 (docs/demo screenshots vs "no edits outside examples/piano/"): the plan's Verification 2
explicitly requires screenshots in docs/demo/. The global constraint binds worker edits; workers
edit only their listed files. The main session writes only the two verification PNGs to docs/demo/.

Ruling 3 (node --test directory): on Node 22, `node --test examples/piano/` fails
("Cannot find module .../examples/piano", directory treated as entry file; checked with a scratch
dir). Equivalent command used for Verification 1: `node --test examples/piano/*.test.mjs`
(runs every test file in the directory). No package.json or runner added (non-goal: build tools).

Ruling 4 (onNote timing, Task 2): "setTimeout offsets from the call" are measured from the play()
call and include the 0.05 s audio lead, so lights match sound: on at (0.05 + start) s, off at
(0.05 + start + duration) s. When one note's end equals the next note's start, the off callback
must fire before the next on (the plan's exact sequence requires it); the timers must be created
so this order is deterministic.

Ruling 5 (AudioContext, Task 3): app.js creates one AudioContext lazily on the first user gesture
(key click, computer key, play button), resumes it if suspended, and passes it as `context` to
every play() call. player.js keeps the plan's `new AudioContext()` default, but the app never
relies on it (avoids one context per note; browsers cap live contexts).

Ruling 6 (server command): Ubuntu has no `python`; `python3 -m http.server` is used, as the run
instructions state.

## Log
Task 1: dispatched [Claude sonnet/medium] orchestra:implementer-medium, start 2026-09-29T13:22:57+0900
Task 2: dispatched [Claude sonnet/high] orchestra:implementer, start 2026-09-29T13:22:57+0900 (parallel with Task 1)
Task 1: worker returned DONE, end ~2026-09-29T13:23:15+0900 (agent duration 18.3 s, 4 tool uses); reviewed 13:24:09
Task 1 review: Spec compliance clean. NOTES names/order/black/freq exactly the plan table (freq === round2(formula) for all 13),
  ODE_TO_JOY JSON-equal to the plan literal, frequencyOf throws Error('Unknown note: ' + name). Tests cover the plan's 4 bullets.
  Scope: only notes.js + notes.test.mjs from this worker (player.test.mjs belongs to concurrent Task 2).
  Minor (deferred, not a spec gap): tests do not assert names/order explicitly; plan's test list does not require it; checked by main session.
  Minor (deferred): report is terse (no cwd/raw output); main session reran the command.
Task 1: complete (workspace changes, review clean, fix rounds 0, tests: node --test examples/piano/notes.test.mjs -> exit 0, 4 pass 0 fail)
Task 2: worker returned DONE, end ~2026-09-29T13:23:49+0900 (agent duration 51.5 s, 5 tool uses); reviewed 13:24:32
Task 2 review: Spec compliance clean. schedule(): RangeError/TypeError with exact messages, cumulative starts
  (end of note i is bit-identical to start of note i+1). play(): lazy `context ??= new AudioContext()`, t0 = currentTime + 0.05,
  triangle osc -> gain -> destination, envelope set(0,at)/lin(0.25,at+0.01)/exp(0.0001,at+0.9d), start(at)/stop(at+d).
  onNote per Ruling 4: one ordered queue [on0,off0,on1,off1,...] drained by a single chained setTimeout with drift
  compensation, so off-before-next-on holds by construction. Tests: schedule example, both error types+messages,
  fake-context play at bpm 6000 (types, freqs in order, start/stop vs t0, gain calls, connect calls, exact onNote sequence),
  extra uneven 6-note alternation test. Main session reran 3x: exit 0, 5 pass each. No leftover processes.
  Minor (deferred): invalid input / missing frequencyOf throws synchronously from play() rather than rejecting the promise;
  an onNote that throws becomes an uncaught timer exception. Neither is in the plan's contract; app.js passes valid input.
  Minor (deferred): fake-context test uses melody [['E4',1],['D4',1]] instead of the schedule example; still exercises the
  end==start tie at bpm 6000.
Task 2: complete (workspace changes, review clean, fix rounds 0, tests: node --test examples/piano/player.test.mjs -> exit 0, 5 pass 0 fail)
Task 3: dispatched [Claude opus/high] orchestra:implementer, start 2026-09-29T13:24:57+0900 (after Tasks 1-2 clean)
Task 3: worker returned DONE, end ~2026-09-29T13:29:50+0900 (agent duration 292.9 s, 25 tool uses); reviewed 13:30:41
Task 3 review: Spec compliance clean. Heading "Orchestra Piano", one-line subtitle, "▶ Play Ode to Joy" button.
  13 <button data-note aria-label> from NOTES; black keys positioned by --at (whites before them), centred on the
  C-D, D-E, F-G, G-A, A-B boundaries (probe: within 1 px at 1280/390/360). Click and A W S E D F T G Y H U J K play
  [[name,1]] at 120 bpm; repeat/Ctrl/Meta/Alt ignored. Play button disabled in try/finally. One lazy AudioContext,
  resume() awaited, passed as context (Ruling 5); none on load. ?pressed lights keys silently, unknown names ignored.
  Ivory radial background, ink serif heading, #D97757 active keys, :focus-visible on all buttons, system fonts only.
  Worker evidence checked: task-3-behavior.log from probe-behavior.mjs uses CDP real input events and an AudioContext
  subclass counter (0 on load, 1 after gestures, reused); task-3-red.log / task-3-green.log present.
  Found and fixed by the worker during its run: 360 px overflow (383 > 360) from the nowrap subtitle widening the body
  grid track -> grid-template-columns: minmax(0, 1fr).
  Minor (deferred): white label text on #D97757 is ~3.1:1 contrast (below 4.5:1 for small text); lit state is transient
    and the note name is also in aria-label; ink text on terracotta (~5.5:1) is the upgrade if wanted.
  Minor (deferred): black-key labels ~8 px at 390 px width; legible in screenshot.
  Minor (deferred): a key lit by ?pressed goes dark after that note is played (screenshot-only feature).
  Minor (deferred): repeated same note (E4,E4) gets off/on in back-to-back timers, so it may look continuously lit.
  Tooling note: the worker's RED run crashed browser-check.mjs (main-session script) before cleanup and left a Chrome;
  the worker killed it. Main session then added crash-path Chrome kill to the script.
Task 3: complete (workspace changes, review clean, fix rounds 0, tests: node --test examples/piano/*.test.mjs -> exit 0, 9 pass; browser check exit 0)

## Final review and verification (main session, 2026-09-29T13:31:32 - 13:32:33 +0900)
Combined change set (all untracked, no tracked file modified, no commit): examples/piano/{notes.js,notes.test.mjs,
  player.js,player.test.mjs,index.html,style.css,app.js} + docs/demo/{piano-desktop.png,piano-mobile.png} (Ruling 2).
  Nothing outside examples/piano/ except the two verification PNGs. Cross-task call path checked: app.js imports only
  NOTES/ODE_TO_JOY/frequencyOf and play; player.js does not import notes.js.
V1: `node --test examples/piano/*.test.mjs` (Ruling 3; bare directory form fails on Node 22) -> exit 0, tests 9, pass 9,
  fail 0. Log: final-node-test.log
V2: `python3 -m http.server 8791 --bind 127.0.0.1 --directory examples/piano` + google-chrome --headless=new via CDP
  (browser-check.mjs) at /?pressed=E4,G4 -> exit 0: 13 button[data-note] at 1280x720, 390x844 and 360x740; active
  exactly E4,G4; aria-label == data-note == visible text; heading, subtitle, play button and keyboard inside viewport;
  scrollWidth == clientWidth (1280/1280, 390/390, 360/360); all 5 black keys on their boundary; console/log problems: [].
  Screenshots: docs/demo/piano-desktop.png (1280x720), docs/demo/piano-mobile.png (390x844), viewed by main session:
  match banner look, E4 and G4 clearly terracotta. Output: final-browser-check.json
V3: not applicable (Ruling 1, no Codex runs). Substitute scope check: git status shows only task-listed files per task.
Cleanup: first final run leaked the http.server (shell `&&`/`&` precedence put it in a subshell) and one Chrome profile
  dir (rmSync raced Chrome exit). Both stopped/removed by the main session, script fixed (await Chrome exit before rm),
  V2 rerun clean. Final `ps` check: no http.server, no Chrome with port 9333, no /tmp/piano-chrome-* left.
Final assessment: APPROVED. No Critical/Important findings; Minors deferred above. Total fix rounds: 0.
