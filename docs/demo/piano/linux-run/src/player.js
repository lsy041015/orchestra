const LEAD = 0.05; // seconds between play() and the first audible sample

export function schedule(melody, bpm) {
  if (typeof bpm !== 'number' || !Number.isFinite(bpm) || bpm <= 0) {
    throw new RangeError('bpm must be a positive number');
  }
  const ok = (p) => Array.isArray(p) && typeof p[0] === 'string' && p[0] !== '' &&
    typeof p[1] === 'number' && Number.isFinite(p[1]) && p[1] > 0;
  if (!Array.isArray(melody) || !melody.every(ok)) {
    throw new TypeError('melody must be [name, beats] pairs');
  }
  const beat = 60 / bpm;
  let start = 0;
  return melody.map(([name, beats]) => {
    const event = { name, start, duration: beats * beat };
    start += event.duration; // next start is exactly this end, so ends and starts tie bit-for-bit
    return event;
  });
}

export function play(melody, { bpm = 120, frequencyOf, onNote = () => {}, context } = {}) {
  const events = schedule(melody, bpm);
  context ??= new AudioContext();
  const t0 = context.currentTime + LEAD;

  for (const { name, start, duration } of events) {
    const at = t0 + start;
    const osc = context.createOscillator();
    const gain = context.createGain();
    osc.type = 'triangle';
    osc.frequency.value = frequencyOf(name);
    gain.gain.setValueAtTime(0, at);
    gain.gain.linearRampToValueAtTime(0.25, at + 0.01);
    gain.gain.exponentialRampToValueAtTime(0.0001, at + duration * 0.9);
    osc.connect(gain);
    gain.connect(context.destination);
    osc.start(at);
    osc.stop(at + duration);
  }

  // One ordered queue drained by a single timer chain: off-before-next-on holds by
  // construction (list order), not by timer or float-rounding luck.
  const queue = events.flatMap(({ name, start, duration }) => [
    { at: LEAD + start, name, on: true },
    { at: LEAD + (start + duration), name, on: false },
  ]);
  const began = performance.now();
  return new Promise((resolve) => {
    let i = 0;
    const next = () => {
      if (i === queue.length) return resolve();
      const wait = queue[i].at * 1000 - (performance.now() - began);
      setTimeout(() => {
        const { name, on } = queue[i++];
        onNote(name, on);
        next();
      }, Math.max(0, wait));
    };
    next();
  });
}
