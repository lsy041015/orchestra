export function schedule(melody, bpm) {
  if (typeof bpm !== 'number' || !Number.isFinite(bpm) || bpm <= 0) {
    throw new RangeError('bpm must be a positive number');
  }
  if (!Array.isArray(melody) || melody.some(pair =>
    !Array.isArray(pair) || pair.length !== 2 ||
    typeof pair[0] !== 'string' || !pair[0].length ||
    typeof pair[1] !== 'number' || !Number.isFinite(pair[1]) || pair[1] <= 0
  )) {
    throw new TypeError('melody must be [name, beats] pairs');
  }

  let start = 0;
  return melody.map(([name, beats]) => {
    const duration = beats * 60 / bpm;
    const event = { name, start, duration };
    start += duration;
    return event;
  });
}

export function play(melody, { bpm = 120, frequencyOf, onNote = () => {}, context } = {}) {
  const events = schedule(melody, bpm);
  if (!events.length) return Promise.resolve();

  const audio = context ?? new AudioContext();
  const t0 = audio.currentTime + 0.05;
  return new Promise(resolve => {
    events.forEach(({ name, start, duration }, index) => {
      const at = t0 + start;
      const oscillator = audio.createOscillator();
      const gain = audio.createGain();
      oscillator.type = 'triangle';
      oscillator.frequency.value = frequencyOf(name);
      oscillator.connect(gain);
      gain.connect(audio.destination);
      gain.gain.setValueAtTime(0, at);
      gain.gain.linearRampToValueAtTime(0.25, at + 0.01);
      gain.gain.exponentialRampToValueAtTime(0.0001, at + duration * 0.9);
      oscillator.start(at);
      oscillator.stop(at + duration);

      setTimeout(() => onNote(name, true), (0.05 + start) * 1000);
      setTimeout(() => {
        onNote(name, false);
        if (index === events.length - 1) resolve();
      }, (0.05 + start + duration) * 1000);
    });
  });
}
