import test from 'node:test';
import assert from 'node:assert/strict';
import { schedule, play } from './player.js';

test('schedule converts beats to consecutive seconds', () => {
  assert.deepEqual(schedule([['E4', 1], ['D4', 0.5]], 120), [
    { name: 'E4', start: 0, duration: 0.5 },
    { name: 'D4', start: 0.5, duration: 0.25 },
  ]);
});

test('schedule rejects invalid bpm', () => {
  for (const bpm of [0, -1, Infinity, NaN, '120']) {
    assert.throws(() => schedule([], bpm), {
      name: 'RangeError', message: 'bpm must be a positive number',
    });
  }
});

test('schedule rejects invalid melody pairs', () => {
  for (const melody of [null, 'E4', [['E4']], [['', 1]], [['E4', 0]], [['E4', Infinity]], [['E4', '1']], [['E4', 1, 2]]]) {
    assert.throws(() => schedule(melody, 120), {
      name: 'TypeError', message: 'melody must be [name, beats] pairs',
    });
  }
});

test('play schedules audio and note callbacks in melody order', async () => {
  const oscillators = [];
  const gains = [];
  const calls = [];
  const destination = {};
  const context = {
    currentTime: 10,
    destination,
    createOscillator() {
      const oscillator = {
        frequency: { value: 0 },
        connect(target) { this.connectedTo = target; },
        start(at) { this.startedAt = at; },
        stop(at) { this.stoppedAt = at; },
      };
      oscillators.push(oscillator);
      return oscillator;
    },
    createGain() {
      const gain = {
        gain: {
          setValueAtTime(...args) { this.initial = args; },
          linearRampToValueAtTime(...args) { this.attack = args; },
          exponentialRampToValueAtTime(...args) { this.release = args; },
        },
        connect(target) { this.connectedTo = target; },
      };
      gains.push(gain);
      return gain;
    },
  };

  await play([['E4', 1], ['D4', 0.5]], {
    bpm: 6000,
    frequencyOf: name => ({ E4: 329.63, D4: 293.66 })[name],
    onNote: (name, active) => calls.push([name, active]),
    context,
  });

  assert.deepEqual(oscillators.map(oscillator => oscillator.frequency.value), [329.63, 293.66]);
  assert.deepEqual(calls, [['E4', true], ['E4', false], ['D4', true], ['D4', false]]);
  for (const [index, oscillator] of oscillators.entries()) {
    const at = 10.05 + (index === 0 ? 0 : 0.01);
    const duration = index === 0 ? 0.01 : 0.005;
    assert.equal(oscillator.type, 'triangle');
    assert.equal(oscillator.connectedTo, gains[index]);
    assert.equal(gains[index].connectedTo, destination);
    assert.equal(oscillator.startedAt, at);
    assert.equal(oscillator.stoppedAt, at + duration);
    assert.deepEqual(gains[index].gain.initial, [0, at]);
    assert.deepEqual(gains[index].gain.attack, [0.25, at + 0.01]);
    assert.deepEqual(gains[index].gain.release, [0.0001, at + duration * 0.9]);
  }
});
