import test from 'node:test';
import assert from 'node:assert/strict';
import { schedule, play } from './player.js';

test('schedule computes start and duration in seconds', () => {
  assert.deepEqual(schedule([['E4', 1], ['D4', 0.5]], 120), [
    { name: 'E4', start: 0, duration: 0.5 },
    { name: 'D4', start: 0.5, duration: 0.25 },
  ]);
});

test('schedule rejects a bad bpm', () => {
  for (const bpm of [0, -1, NaN, Infinity, '120', undefined]) {
    assert.throws(() => schedule([['E4', 1]], bpm), (e) =>
      e instanceof RangeError && e.message === 'bpm must be a positive number');
  }
});

test('schedule rejects a bad melody', () => {
  const bad = [null, 'E4', [['E4']], [['', 1]], [[4, 1]], [['E4', 0]], [['E4', -1]], [['E4', NaN]], [['E4', '1']], ['E4'], [null]];
  for (const melody of bad) {
    assert.throws(() => schedule(melody, 120), (e) =>
      e instanceof TypeError && e.message === 'melody must be [name, beats] pairs');
  }
});

function fakeContext() {
  const log = { oscillators: [], gains: [], connects: [] };
  const param = (calls) => ({
    value: undefined,
    setValueAtTime: (...a) => calls.push(['set', ...a]),
    linearRampToValueAtTime: (...a) => calls.push(['lin', ...a]),
    exponentialRampToValueAtTime: (...a) => calls.push(['exp', ...a]),
  });
  const context = {
    currentTime: 2,
    destination: { id: 'destination' },
    createOscillator() {
      const o = { type: undefined, frequency: param([]), starts: [], stops: [] };
      o.start = (t) => o.starts.push(t);
      o.stop = (t) => o.stops.push(t);
      o.connect = (n) => log.connects.push([o, n]);
      log.oscillators.push(o);
      return o;
    },
    createGain() {
      const calls = [];
      const g = { gain: param(calls), calls };
      g.connect = (n) => log.connects.push([g, n]);
      log.gains.push(g);
      return g;
    },
  };
  return { context, log };
}

test('play drives the audio graph and reports notes in order', async () => {
  const { context, log } = fakeContext();
  const freqs = { E4: 330, D4: 294 };
  const calls = [];
  await play([['E4', 1], ['D4', 1]], {
    bpm: 6000,
    context,
    frequencyOf: (n) => freqs[n],
    onNote: (name, on) => calls.push([name, on]),
  });

  const t0 = 2 + 0.05;
  const d = 0.01;
  assert.deepEqual(log.oscillators.map((o) => o.type), ['triangle', 'triangle']);
  assert.deepEqual(log.oscillators.map((o) => o.frequency.value), [330, 294]);
  assert.deepEqual(log.oscillators.map((o) => o.starts), [[t0], [t0 + d]]);
  assert.deepEqual(log.oscillators.map((o) => o.stops), [[t0 + d], [t0 + d + d]]);
  assert.deepEqual(log.gains[0].calls, [
    ['set', 0, t0],
    ['lin', 0.25, t0 + 0.01],
    ['exp', 0.0001, t0 + d * 0.9],
  ]);
  assert.deepEqual(log.gains[1].calls[0], ['set', 0, t0 + d]);
  for (let i = 0; i < 2; i++) {
    assert.deepEqual(log.connects.filter(([from]) => from === log.oscillators[i]), [[log.oscillators[i], log.gains[i]]]);
    assert.deepEqual(log.connects.filter(([from]) => from === log.gains[i]), [[log.gains[i], context.destination]]);
  }
  assert.deepEqual(calls, [['E4', true], ['E4', false], ['D4', true], ['D4', false]]);
});

test('play always turns a note off before the next one turns on', async () => {
  const { context } = fakeContext();
  const names = ['C4', 'D4', 'E4', 'F4', 'G4', 'A4'];
  const melody = names.map((n, i) => [n, [0.1, 0.3, 0.7, 0.2, 0.6, 0.9][i]]);
  const calls = [];
  await play(melody, { bpm: 6000, context, frequencyOf: () => 440, onNote: (n, on) => calls.push([n, on]) });
  assert.deepEqual(calls, names.flatMap((n) => [[n, true], [n, false]]));
});
