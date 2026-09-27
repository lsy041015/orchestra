export const NOTES = [
  { name: 'C4', freq: 261.63, black: false },
  { name: 'C#4', freq: 277.18, black: true },
  { name: 'D4', freq: 293.66, black: false },
  { name: 'D#4', freq: 311.13, black: true },
  { name: 'E4', freq: 329.63, black: false },
  { name: 'F4', freq: 349.23, black: false },
  { name: 'F#4', freq: 369.99, black: true },
  { name: 'G4', freq: 392.0, black: false },
  { name: 'G#4', freq: 415.3, black: true },
  { name: 'A4', freq: 440.0, black: false },
  { name: 'A#4', freq: 466.16, black: true },
  { name: 'B4', freq: 493.88, black: false },
  { name: 'C5', freq: 523.25, black: false },
];

export const ODE_TO_JOY = [
  ['E4', 1], ['E4', 1], ['F4', 1], ['G4', 1],
  ['G4', 1], ['F4', 1], ['E4', 1], ['D4', 1],
  ['C4', 1], ['C4', 1], ['D4', 1], ['E4', 1],
  ['E4', 1.5], ['D4', 0.5], ['D4', 2],
];

export function frequencyOf(name) {
  const note = NOTES.find((n) => n.name === name);
  if (!note) throw new Error('Unknown note: ' + name);
  return note.freq;
}
