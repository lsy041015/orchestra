import { NOTES, ODE_TO_JOY, frequencyOf } from './notes.js';
import { play } from './player.js';

const COMPUTER_KEYS = 'awsedftgyhujk'; // C4..C5 in NOTES order
const keyboard = document.querySelector('.keyboard');
const playButton = document.querySelector('.play');
const keys = new Map();
const sounding = new Map(); // count per note, so an overlapping repeat does not unlight early

let whites = 0;
for (const { name, black } of NOTES) {
  const button = document.createElement('button');
  button.type = 'button';
  button.className = black ? 'key black' : 'key white';
  button.dataset.note = name;
  button.setAttribute('aria-label', name);
  button.textContent = name;
  if (black) button.style.setProperty('--at', whites); // sits on the boundary after `whites` white keys
  else whites++;
  button.addEventListener('click', () => sound([[name, 1]]).catch(console.error));
  keyboard.append(button);
  keys.set(name, button);
}

function light(name, on) {
  const count = (sounding.get(name) ?? 0) + (on ? 1 : -1);
  sounding.set(name, count);
  keys.get(name).classList.toggle('is-active', count > 0);
}

let context; // created on the first user gesture only; browsers block audio before that
async function sound(melody) {
  context ??= new AudioContext();
  if (context.state === 'suspended') await context.resume();
  return play(melody, { bpm: 120, frequencyOf, onNote: light, context });
}

addEventListener('keydown', (event) => {
  if (event.repeat || event.ctrlKey || event.metaKey || event.altKey || event.key.length !== 1) return;
  const i = COMPUTER_KEYS.indexOf(event.key.toLowerCase());
  if (i >= 0) sound([[NOTES[i].name, 1]]).catch(console.error);
});

playButton.addEventListener('click', async () => {
  playButton.disabled = true;
  try {
    await sound(ODE_TO_JOY);
  } catch (error) {
    console.error(error);
  } finally {
    playButton.disabled = false;
  }
});

const pressed = new URLSearchParams(location.search).get('pressed');
for (const name of pressed ? pressed.split(',') : []) keys.get(name.trim())?.classList.add('is-active');
