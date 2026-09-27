import { NOTES, ODE_TO_JOY, frequencyOf } from './notes.js';
import { play } from './player.js';

const KEYMAP = 'AWSEDFTGYHUJK'; // C4..C5 in NOTES order
const keyboard = document.getElementById('keyboard');
const playButton = document.getElementById('play');
const buttons = new Map();
const sounding = new Map(); // note -> overlapping soundings, so a repeat does not unlight early

let whiteCount = 0;
for (const { name, black } of NOTES) {
  const button = document.createElement('button');
  button.type = 'button';
  button.classList.add('key', black ? 'black' : 'white');
  button.dataset.note = name;
  button.setAttribute('aria-label', name);
  button.textContent = name;
  // A black key sits on the boundary after the white keys that precede it.
  if (black) button.style.setProperty('--at', whiteCount);
  else whiteCount++;
  button.addEventListener('click', () => playNote(name));
  keyboard.append(button);
  buttons.set(name, button);
}

// Screenshot hook: ?pressed=E4,G4 lights those keys without sound.
const pressed = new URLSearchParams(location.search).get('pressed');
for (const name of pressed ? pressed.split(',') : []) buttons.get(name.trim())?.classList.add('is-active');

let context;
function audio() {
  // Created on the first user gesture to satisfy browser autoplay policy.
  context ??= new AudioContext();
  if (context.state === 'suspended') context.resume();
  return context;
}

function onNote(name, on) {
  const count = (sounding.get(name) || 0) + (on ? 1 : -1);
  sounding.set(name, count);
  const button = buttons.get(name);
  if (!button) return;
  button.classList.toggle('is-active', count > 0);
  if (on) {
    // Restart the strike animation so a repeated note visibly re-strikes a lit key.
    button.classList.remove('is-struck');
    void button.offsetWidth; // force reflow so the animation restarts
    button.classList.add('is-struck');
  }
}

function playNote(name) {
  play([[name, 1]], { bpm: 120, frequencyOf, onNote, context: audio() });
}

document.addEventListener('keydown', (event) => {
  if (event.repeat || event.ctrlKey || event.metaKey || event.altKey) return;
  const index = KEYMAP.indexOf(event.key.toUpperCase());
  if (event.key.length === 1 && index !== -1) playNote(NOTES[index].name);
});

playButton.addEventListener('click', async () => {
  playButton.disabled = true;
  try {
    await play(ODE_TO_JOY, { bpm: 120, frequencyOf, onNote, context: audio() });
  } finally {
    playButton.disabled = false;
  }
});
