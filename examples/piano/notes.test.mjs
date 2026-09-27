import test from 'node:test';
import assert from 'node:assert/strict';
import { NOTES, ODE_TO_JOY, frequencyOf } from './notes.js';

test('notes cover C4 through C5 with exact frequency data', () => {
  assert.equal(NOTES.length, 13);
  assert.equal(NOTES.filter(({ black }) => !black).length, 8);
  for (const [index, { name, freq }] of NOTES.entries()) {
    const n = index - 9;
    assert.ok(Math.abs(freq - 440 * 2 ** (n / 12)) <= 0.01, `${name} frequency`);
  }
});

test('Ode to Joy uses known notes and totals 16 beats', () => {
  const names = new Set(NOTES.map(({ name }) => name));
  assert.ok(ODE_TO_JOY.every(([name]) => names.has(name)));
  assert.equal(ODE_TO_JOY.reduce((sum, [, beats]) => sum + beats, 0), 16);
});

test('frequencyOf returns frequencies and rejects unknown notes', () => {
  assert.equal(frequencyOf('A4'), 440);
  assert.throws(() => frequencyOf('H9'), { message: 'Unknown note: H9' });
});
