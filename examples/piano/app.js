import { NOTES, ODE_TO_JOY, frequencyOf } from './notes.js';
import { play } from './player.js';

const keyboard = document.getElementById('keyboard');
const playButton = document.getElementById('play');
const keys = new Map();
const computerKeys = 'AWSEDFTGYHUJK';
let whiteCount = 0;
let audio;

for (const note of NOTES) {
  const key = document.createElement('button');
  key.type = 'button';
  key.className = `key ${note.black ? 'black' : 'white'}`;
  key.dataset.note = note.name;
  key.setAttribute('aria-label', note.name);
  key.textContent = note.name;
  if (note.black) key.style.setProperty('--left', `${whiteCount * 12.5}%`);
  else whiteCount++;
  key.addEventListener('click', () => playNote(note.name));
  keyboard.append(key);
  keys.set(note.name, key);
}

for (const name of new URLSearchParams(location.search).get('pressed')?.split(',') ?? []) {
  keys.get(name)?.classList.add('is-active');
}

function context() {
  audio ??= new AudioContext();
  if (audio.state === 'suspended') audio.resume();
  return audio;
}

function light(name, active) {
  const key = keys.get(name);
  if (!key) return;
  if (active) {
    key.classList.remove('is-striking');
    void key.offsetWidth;
    key.classList.add('is-active', 'is-striking');
  } else {
    key.classList.remove('is-active', 'is-striking');
  }
}

function playNote(name) {
  play([[name, 1]], { bpm: 120, frequencyOf, onNote: light, context: context() });
}

document.addEventListener('keydown', (event) => {
  if (event.repeat || event.ctrlKey || event.altKey || event.metaKey) return;
  const index = computerKeys.indexOf(event.key.toUpperCase());
  if (index !== -1) playNote(NOTES[index].name);
});

playButton.addEventListener('click', async () => {
  playButton.disabled = true;
  try {
    await play(ODE_TO_JOY, { bpm: 120, frequencyOf, onNote: light, context: context() });
  } finally {
    playButton.disabled = false;
  }
});
