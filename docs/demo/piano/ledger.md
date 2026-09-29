Plan: docs/orchestra/plans/2026-09-27-piano-demo-plan.md
Routing: Easy=Codex gpt-6-luna/medium, Medium=Codex gpt-6-sol/medium, UI=Codex gpt-6-sol/high (user choice, 2026-09-27)
BASE: 910ae7e
Parallel: Task 1 and Task 2 run together (no shared files); Task 3 after both.
Task 1: Codex thread 01a0e340-75b1-7391-9517-c5162d06d7ec (gpt-6-luna/medium, 23:24:07-23:25:21, 74 s)
Task 1: Scope reported "outside allowed: examples/piano/player.js" -> file belongs to concurrent Task 2's allowed list; ignored per parallel rule.
Task 1: complete (workspace changes, review clean: NOTES/ODE_TO_JOY match plan exactly, 4/4 test bullets covered; tests: node --test examples/piano/notes.test.mjs -> 3 pass)
Task 2: Codex thread 01a0e340-7a56-7eb1-9e7a-53f7d7f1edfc (gpt-6-sol/medium, 23:24:08-23:26:39, 151 s)
Task 2: Scope reported "outside allowed: examples/piano/notes.js, examples/piano/notes.test.mjs" -> concurrent Task 1 files; ignored per parallel rule.
Ruling: plan gap - no package.json, so Node 18/20 load examples/piano/*.js as CommonJS (Task 1 test would fail there; Task 2 worked around it with a data: URL import). Main session adds examples/piano/package.json {"private":true,"type":"module"} inline and fixes the plan's verification command to node --test "examples/piano/*.test.mjs" (a bare directory is run as a file and fails). Cost if wrong: one extra 4-line file.
Task 2 review: Important - player.test.mjs data: URL import is a workaround for the gap above; replace with a normal import. Minor (deferred) - onNote end/start timers of adjacent notes rely on equal float sums; exact at 120 bpm.
Task 2 fix 1: --resume 01a0e340-7a56-7eb1-9e7a-53f7d7f1edfc (gpt-6-sol/medium, 23:27:39-23:28:22, 43 s), Scope: ok
Task 2 re-review: Finding 1 ADDRESSED (player.test.mjs:3 plain import, readFile removed). New breakage: None. Verdict: CLEAN
Task 2: complete (workspace changes, review clean after 1 fix round; tests: node --test "examples/piano/*.test.mjs" -> 7 pass)
Task 3: Codex thread 01a0e343-b784-7691-86a0-45ba47e9230f (gpt-6-sol/high, 23:27:40-23:32:51, 311 s)
Task 3: Scope reported "outside allowed: examples/piano/player.test.mjs" -> concurrent Task 2 fix file; ignored per parallel rule.
Task 3 review (headless Chrome over http.server, CDP): 13 keys / 8 white, ?pressed=E4,G4 lit, C5 click lit, key 'd' -> E4, melody highlight order E E F G G F E D C, button disabled during playback and re-enabled, overflowX 0 at 1280/390/360.
Task 3 findings: (1) Important - .key.white + .key.white misses whites separated by black keys in DOM -> doubled borders at C|D D|E F|G G|A A|B. (2) Minor - favicon.ico 404 console error. (3) Important for demo - repeated notes stay lit, second strike invisible.
Task 3 fix 1: --resume 01a0e343-b784-7691-86a0-45ba47e9230f (gpt-6-sol/high, 23:34:23-23:37:35, 192 s), Scope: ok
Task 3 re-review (CDP): Finding 1 ADDRESSED (white border-left 1px,0,0,0,0,0,0,0). Finding 2 ADDRESSED (0 console problems). Finding 3 ADDRESSED (15 strike animations = melody order incl. repeats). New breakage: None. Verdict: CLEAN
Task 3: complete (workspace changes, review clean after 1 fix round; tests: node --test "examples/piano/*.test.mjs" -> 7 pass; browser checks above)
