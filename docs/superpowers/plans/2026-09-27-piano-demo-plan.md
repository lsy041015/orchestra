# Orchestra Piano Demo Plan

## Context and goal

Orchestra needs one recorded end-to-end run: plan → tier table → routing →
Claude and Codex workers → main-session review → ledger. The demo result must
be easy to judge by eye: a one-octave web piano that plays *Ode to Joy* and
lights up each key as it sounds.

Non-goals: build tools, dependencies, recording audio, more than one octave,
sharps in the melody.

## Global constraints

- Plain ES modules, no dependencies, no build step. Node.js 18+ `node --test`
  for tests. Browsers load the page over HTTP
  (`python -m http.server` in `examples/piano/`).
- Only the files listed in each task. No edits outside `examples/piano/`.
- Web Audio is created lazily on the first user gesture (autoplay policy).
- Keys are real `<button>` elements with visible focus; the page works at
  360 px width without horizontal scrolling.
- No git commit, push, reset or checkout by workers.

## Interfaces and dependencies

Task 1 and Task 2 are independent and may run in parallel. Task 3 consumes both.

`examples/piano/notes.js` (Task 1):

```js
export const NOTES;       // 13 entries, C4..C5 chromatic, in order
                          // { name: 'C4', freq: 261.63, black: false }
export const ODE_TO_JOY;  // array of [noteName, beats]
export function frequencyOf(name); // number; throws Error(`Unknown note: ${name}`)
```

`examples/piano/player.js` (Task 2):

```js
export function schedule(melody, bpm);
// -> [{ name, start, duration }] in seconds, beat = 60 / bpm,
//    start = sum of previous durations.
export function play(melody, { bpm = 120, frequencyOf, onNote = () => {}, context } = {});
// -> Promise<void> resolved after the last note ends.
```

### Task 1: Note table and melody

Tier: Easy. Files: `examples/piano/notes.js`, `examples/piano/notes.test.mjs`.

`NOTES`, exactly, in this order (`freq` = 440 × 2^((n − 9) / 12) for index n,
rounded to 2 decimals):

| name | freq | black |
|---|---|---|
| C4 | 261.63 | false |
| C#4 | 277.18 | true |
| D4 | 293.66 | false |
| D#4 | 311.13 | true |
| E4 | 329.63 | false |
| F4 | 349.23 | false |
| F#4 | 369.99 | true |
| G4 | 392.00 | false |
| G#4 | 415.30 | true |
| A4 | 440.00 | false |
| A#4 | 466.16 | true |
| B4 | 493.88 | false |
| C5 | 523.25 | false |

`ODE_TO_JOY`, exactly:
`[['E4',1],['E4',1],['F4',1],['G4',1],['G4',1],['F4',1],['E4',1],['D4',1],['C4',1],['C4',1],['D4',1],['E4',1],['E4',1.5],['D4',0.5],['D4',2]]`

`frequencyOf(name)` returns the matching `freq`, or throws
`new Error('Unknown note: ' + name)`.

Tests (`notes.test.mjs`, `node:test` + `node:assert/strict`):
- 13 notes, 8 with `black: false`;
- each `freq` equals the formula within 0.01;
- every melody note exists in `NOTES`, total beats = 16;
- `frequencyOf('A4') === 440`, and `frequencyOf('H9')` throws `Unknown note: H9`.

Command: `node --test examples/piano/notes.test.mjs` → all pass.

### Task 2: Scheduler and Web Audio player

Tier: Medium. Files: `examples/piano/player.js`, `examples/piano/player.test.mjs`.
Does not import `notes.js`; the caller passes `frequencyOf`.

`schedule(melody, bpm)`:
- throws `RangeError('bpm must be a positive number')` unless `bpm` is a finite
  number > 0;
- throws `TypeError('melody must be [name, beats] pairs')` unless `melody` is
  an array whose items are `[non-empty string, finite number > 0]`;
- `schedule([['E4',1],['D4',0.5]], 120)` →
  `[{ name: 'E4', start: 0, duration: 0.5 }, { name: 'D4', start: 0.5, duration: 0.25 }]`.

`play(melody, options)`:
- uses `schedule`; `context` defaults to `new AudioContext()`;
- per event, from `t0 = context.currentTime + 0.05`: one `OscillatorNode`
  (`type = 'triangle'`, `frequency.value = frequencyOf(name)`) through one
  `GainNode`; gain `setValueAtTime(0, at)`, `linearRampToValueAtTime(0.25, at + 0.01)`,
  `exponentialRampToValueAtTime(0.0001, at + duration * 0.9)`; oscillator
  `start(at)` and `stop(at + duration)`;
- calls `onNote(name, true)` at the note's start and `onNote(name, false)` at
  its end using `setTimeout` offsets from the call; resolves after the last
  `onNote(..., false)`.

Tests (`player.test.mjs`, `node:test`): the `schedule` example above, both
error cases, and `play` with a fake context (records oscillator frequencies,
start/stop times and connect calls) at `bpm = 6000`, asserting frequencies in
melody order and the exact `onNote` call sequence
`[['E4',true],['E4',false],['D4',true],['D4',false]]`.

Command: `node --test examples/piano/player.test.mjs` → all pass.

### Task 3: Piano page

Tier: Hard (UI). Files: `examples/piano/index.html`, `examples/piano/style.css`,
`examples/piano/app.js`. Consumes Task 1 and Task 2 exports only.

- Heading "Orchestra Piano", a one-line subtitle, the keyboard, and a
  `▶ Play Ode to Joy` button.
- Keyboard rendered from `NOTES`: 8 white keys side by side, 5 black keys
  overlaid at the standard positions between C–D, D–E, F–G, G–A, A–B. Each key
  is a `<button data-note="C4" aria-label="C4">` showing its name.
- Clicking or tapping a key plays that note for 1 beat at 120 bpm and lights it.
- Computer keys `A W S E D F T G Y H U J K` map to C4..C5 in order.
- The play button plays `ODE_TO_JOY` at 120 bpm, lights each key while it
  sounds (`is-active` class), and is disabled while playing.
- `?pressed=E4,G4` lights those keys on load without sound (for screenshots).
- Style matches the README banner: ivory paper background, dark ink text,
  terracotta (`#D97757`) for active keys. Responsive down to 360 px.

Checks by the main session: page served over HTTP renders 13 keys with no
console errors; screenshots at 1280×720 and 390×844 with `?pressed=E4,G4`.

## Verification

1. `node --test examples/piano/` → all pass.
2. Headless Chrome over `python -m http.server`: DOM has 13
   `button[data-note]`, `E4` and `G4` carry `is-active` with `?pressed=E4,G4`,
   console shows no errors; desktop and mobile screenshots saved to
   `docs/demo/`.
3. Codex runs report `Scope: ok` (or only files of a concurrently running
   worker).

## Review focus and recovery

- Exact data values, envelope timing and `onNote` order.
- Black-key positions and the 360 px layout.
- On failure: send the concrete finding to the same worker (`SendMessage` for
  Claude, `--resume <thread>` for Codex). Two failed rounds with one root cause
  → main-session `Ruling:`.
