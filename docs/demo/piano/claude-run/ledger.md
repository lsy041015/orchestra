Plan: docs/orchestra/plans/2026-09-27-piano-demo-plan.md
Run: B (Claude-only comparison). Same plan, same start commit 910ae7e, same task briefs as run A.
Routing: Easy=Claude sonnet/medium, Medium=Claude sonnet/high, UI=Claude opus/high (user's saved preference: simple=Sonnet medium, dev=Sonnet high, UI=Opus high)
BASE: 910ae7e
Parallel: Task 1 and Task 2 together; Task 3 after both.
Task 1: Claude sonnet/medium (orchestra:implementer-medium), 00:10:33-00:12:07, 94 s, 9 tool uses
Task 1: complete (workspace changes; review clean: NOTES/ODE_TO_JOY numerically equal to plan, 4/4 test bullets; tests: node --test examples/piano/notes.test.mjs -> 4 pass)
Task 2: Claude sonnet/high (orchestra:implementer), 00:11:14-00:15:59, 287 s, 17 tool uses
Ruling: same plan gap as run A (no package.json -> Node 18/20 read examples/piano/*.js as CommonJS). Main session adds examples/piano/package.json {"private":true,"type":"module"} inline, identical to run A. Worker also flagged the wrong plan command `node --test examples/piano/`.
Task 2: complete (workspace changes; review clean, no fix round: plain import, errors/envelope/onNote order match plan; tests: node --test "examples/piano/*.test.mjs" -> 8 pass)
Task 3: Claude opus/high (orchestra:implementer, model opus), 00:16:59-00:20:37, 217 s, 21 tool uses
Task 3 review (same CDP harness as run A): 13 keys / 8 white, ?pressed lit, C5 click, key 'd' -> E4, melody order, button disabled/re-enabled, overflowX 0 at 1280/390/360, white borders single (1px,0...), console problems 0 (favicon link present). Overlapping presses of one key handled by a counter.
Task 3 findings: (1) Important for demo - repeated notes stay lit, second strike invisible (same as run A finding 3). (2) Minor - worker wrote scratchpad/piano-app-check.mjs outside the allowed files (outside the repo). Not requested to change.
Task 3 fix 1: SendMessage to the same worker, 00:21:39-00:22:59, 79 s, 8 tool uses
Task 3 re-review (CDP): Finding 1 ADDRESSED (15 strike animations = melody order incl. repeats). New breakage: None. Verdict: CLEAN
Task 3: complete (workspace changes, review clean after 1 fix round; tests: node --test in examples/piano -> 8 pass; browser checks above)
