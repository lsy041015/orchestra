// Melody scheduler and Web Audio player. Does not import notes.js — callers
// pass a `frequencyOf` function so this module stays reusable/testable.

export function schedule(melody, bpm) {
  if (typeof bpm !== 'number' || !Number.isFinite(bpm) || bpm <= 0) {
    throw new RangeError('bpm must be a positive number');
  }
  if (
    !Array.isArray(melody) ||
    !melody.every(
      (item) =>
        Array.isArray(item) &&
        item.length === 2 &&
        typeof item[0] === 'string' &&
        item[0].length > 0 &&
        typeof item[1] === 'number' &&
        Number.isFinite(item[1]) &&
        item[1] > 0
    )
  ) {
    throw new TypeError('melody must be [name, beats] pairs');
  }

  const beat = 60 / bpm;
  let start = 0;
  return melody.map(([name, beats]) => {
    const duration = beats * beat;
    const event = { name, start, duration };
    start += duration;
    return event;
  });
}

export function play(melody, { bpm = 120, frequencyOf, onNote = () => {}, context } = {}) {
  const ctx = context || new AudioContext();
  const events = schedule(melody, bpm);
  const t0 = ctx.currentTime + 0.05;

  for (const { name, start, duration } of events) {
    const at = t0 + start;

    const oscillator = ctx.createOscillator();
    oscillator.type = 'triangle';
    oscillator.frequency.value = frequencyOf(name);

    const gain = ctx.createGain();
    gain.gain.setValueAtTime(0, at);
    gain.gain.linearRampToValueAtTime(0.25, at + 0.01);
    gain.gain.exponentialRampToValueAtTime(0.0001, at + duration * 0.9);

    oscillator.connect(gain);
    gain.connect(ctx.destination);

    oscillator.start(at);
    oscillator.stop(at + duration);
  }

  return new Promise((resolve) => {
    let lastOffMs = 0;
    for (const { name, start, duration } of events) {
      const onMs = (0.05 + start) * 1000;
      const offMs = (0.05 + start + duration) * 1000;
      setTimeout(() => onNote(name, true), onMs);
      setTimeout(() => onNote(name, false), offMs);
      lastOffMs = Math.max(lastOffMs, offMs);
    }
    setTimeout(resolve, lastOffMs);
  });
}
