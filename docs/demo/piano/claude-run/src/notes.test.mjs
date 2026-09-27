import test from 'node:test';
import assert from 'node:assert/strict';
import { NOTES, ODE_TO_JOY, frequencyOf } from './notes.js';

test('NOTES has 13 notes, 8 natural (black: false)', () => {
  assert.equal(NOTES.length, 13);
  assert.equal(NOTES.filter((n) => n.black === false).length, 8);
});

test('each NOTES freq matches 440 * 2^((n-9)/12) within 0.01', () => {
  NOTES.forEach((note, n) => {
    const expected = 440 * Math.pow(2, (n - 9) / 12);
    assert.ok(
      Math.abs(note.freq - expected) < 0.01,
      `${note.name}: expected ~${expected}, got ${note.freq}`
    );
  });
});

test('ODE_TO_JOY notes all exist in NOTES and total beats is 16', () => {
  const names = new Set(NOTES.map((n) => n.name));
  let total = 0;
  ODE_TO_JOY.forEach(([name, beats]) => {
    assert.ok(names.has(name), `${name} not in NOTES`);
    total += beats;
  });
  assert.equal(total, 16);
});

test('frequencyOf returns freq for known note and throws for unknown', () => {
  assert.equal(frequencyOf('A4'), 440);
  assert.throws(() => frequencyOf('H9'), { message: 'Unknown note: H9' });
});
