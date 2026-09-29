import test from 'node:test';
import assert from 'node:assert/strict';
import { NOTES, ODE_TO_JOY, frequencyOf } from './notes.js';

test('13 notes, 8 white', () => {
  assert.equal(NOTES.length, 13);
  assert.equal(NOTES.filter((n) => !n.black).length, 8);
});

test('freq matches equal temperament', () => {
  NOTES.forEach((n, i) => {
    assert.ok(Math.abs(n.freq - 440 * 2 ** ((i - 9) / 12)) <= 0.01, n.name);
  });
});

test('melody notes exist and total 16 beats', () => {
  const names = new Set(NOTES.map((n) => n.name));
  for (const [name] of ODE_TO_JOY) assert.ok(names.has(name), name);
  assert.equal(ODE_TO_JOY.reduce((s, [, b]) => s + b, 0), 16);
});

test('frequencyOf', () => {
  assert.equal(frequencyOf('A4'), 440);
  assert.throws(() => frequencyOf('H9'), { message: 'Unknown note: H9' });
});
