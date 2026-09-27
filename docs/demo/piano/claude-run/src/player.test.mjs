import { test } from 'node:test';
import assert from 'node:assert/strict';
import { schedule, play } from './player.js';

test('schedule computes start/duration in seconds from bpm', () => {
  const result = schedule([['E4', 1], ['D4', 0.5]], 120);
  assert.deepEqual(result, [
    { name: 'E4', start: 0, duration: 0.5 },
    { name: 'D4', start: 0.5, duration: 0.25 },
  ]);
});

test('schedule rejects a non-positive or non-finite bpm', () => {
  assert.throws(
    () => schedule([['E4', 1]], 0),
    { name: 'RangeError', message: 'bpm must be a positive number' }
  );
  assert.throws(
    () => schedule([['E4', 1]], -5),
    { name: 'RangeError', message: 'bpm must be a positive number' }
  );
  assert.throws(
    () => schedule([['E4', 1]], NaN),
    { name: 'RangeError', message: 'bpm must be a positive number' }
  );
  assert.throws(
    () => schedule([['E4', 1]], Infinity),
    { name: 'RangeError', message: 'bpm must be a positive number' }
  );
});

test('schedule rejects a malformed melody', () => {
  const expected = { name: 'TypeError', message: 'melody must be [name, beats] pairs' };
  assert.throws(() => schedule('not an array', 120), expected);
  assert.throws(() => schedule([['', 1]], 120), expected);
  assert.throws(() => schedule([['E4', 0]], 120), expected);
  assert.throws(() => schedule([['E4', -1]], 120), expected);
  assert.throws(() => schedule([['E4', NaN]], 120), expected);
  assert.throws(() => schedule([[4, 1]], 120), expected);
  assert.throws(() => schedule([['E4']], 120), expected);
});

// Fake Web Audio graph: records what play() does without any real audio.
function makeFakeContext() {
  const calls = { oscillators: [], connects: [] };
  const context = {
    currentTime: 0,
    createOscillator() {
      const osc = {
        type: undefined,
        frequency: { value: undefined },
        connect(dest) {
          calls.connects.push({ from: 'oscillator', to: dest });
        },
        start(at) {
          osc.startedAt = at;
        },
        stop(at) {
          osc.stoppedAt = at;
        },
      };
      calls.oscillators.push(osc);
      return osc;
    },
    createGain() {
      const gain = {
        gain: {
          setValueAtTime(value, at) {
            gain.gain.log = gain.gain.log || [];
            gain.gain.log.push(['setValueAtTime', value, at]);
          },
          linearRampToValueAtTime(value, at) {
            gain.gain.log.push(['linearRampToValueAtTime', value, at]);
          },
          exponentialRampToValueAtTime(value, at) {
            gain.gain.log.push(['exponentialRampToValueAtTime', value, at]);
          },
        },
        connect(dest) {
          calls.connects.push({ from: 'gain', to: dest });
        },
      };
      return gain;
    },
    destination: 'destination',
  };
  return { context, calls };
}

test('play drives the Web Audio graph and reports notes in order', async () => {
  const { context, calls } = makeFakeContext();
  const frequencies = { E4: 329.63, D4: 293.66 };
  const frequencyOf = (name) => frequencies[name];
  const notifications = [];

  await play([['E4', 1], ['D4', 0.5]], {
    bpm: 6000, // beat = 0.01s, so the whole test resolves fast
    frequencyOf,
    onNote: (name, on) => notifications.push([name, on]),
    context,
  });

  assert.equal(calls.oscillators.length, 2);
  assert.equal(calls.oscillators[0].type, 'triangle');
  assert.equal(calls.oscillators[0].frequency.value, 329.63);
  assert.equal(calls.oscillators[1].type, 'triangle');
  assert.equal(calls.oscillators[1].frequency.value, 293.66);

  // Each oscillator connects to a gain node, which connects to destination.
  assert.equal(calls.connects.length, 4);
  assert.equal(calls.connects[0].from, 'oscillator');
  assert.equal(calls.connects[1].from, 'gain');
  assert.equal(calls.connects[1].to, 'destination');

  const t0 = 0.05;
  const beat = 60 / 6000;
  const at0 = t0;
  const at1 = t0 + beat;
  assert.equal(calls.oscillators[0].startedAt, at0);
  assert.equal(calls.oscillators[0].stoppedAt, at0 + beat);
  assert.equal(calls.oscillators[1].startedAt, at1);
  assert.equal(calls.oscillators[1].stoppedAt, at1 + beat * 0.5);

  assert.deepEqual(notifications, [
    ['E4', true],
    ['E4', false],
    ['D4', true],
    ['D4', false],
  ]);
});
