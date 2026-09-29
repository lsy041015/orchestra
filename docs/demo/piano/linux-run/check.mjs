// Headless Chrome checks for the piano demo: the items runs A and B checked, plus the
// animation frames a repeated note stays dark between strikes (0 = the second strike is invisible).
// Usage: node check.mjs <site dir> <existing screenshot dir>   (needs google-chrome and python3)
import { spawn } from 'node:child_process';
import { mkdtempSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import net from 'node:net';
import path from 'node:path';

const [siteDir, outDir] = process.argv.slice(2);
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const freePort = () => new Promise((resolve) => {
  const s = net.createServer().listen(0, '127.0.0.1', () => { const { port } = s.address(); s.close(() => resolve(port)); });
});

const httpPort = await freePort();
const cdpPort = await freePort();
const profile = mkdtempSync(path.join(tmpdir(), 'piano-cdp-'));
const server = spawn('python3', ['-m', 'http.server', String(httpPort), '--bind', '127.0.0.1'], { cwd: siteDir, stdio: 'ignore' });
const chrome = spawn('google-chrome', ['--headless=new', `--remote-debugging-port=${cdpPort}`, `--user-data-dir=${profile}`,
  '--no-first-run', '--no-default-browser-check', 'about:blank'], { stdio: 'ignore' });

try {
  let targets;
  for (let i = 0; i < 50 && !targets; i++) {
    try { targets = await (await fetch(`http://127.0.0.1:${cdpPort}/json`)).json(); } catch { await sleep(200); }
  }
  const ws = new WebSocket(targets.find((t) => t.type === 'page').webSocketDebuggerUrl);
  await new Promise((r) => ws.addEventListener('open', r, { once: true }));
  let id = 0;
  const pending = new Map();
  const problems = [];
  ws.addEventListener('message', ({ data }) => {
    const msg = JSON.parse(data);
    if (pending.has(msg.id)) { pending.get(msg.id)(msg); pending.delete(msg.id); }
    if (msg.method === 'Runtime.exceptionThrown') problems.push(msg.params.exceptionDetails.text);
    if (msg.method === 'Runtime.consoleAPICalled' && msg.params.type === 'error') problems.push('console.error');
    if (msg.method === 'Log.entryAdded' && msg.params.entry.level === 'error') {
      problems.push(`${msg.params.entry.text} ${msg.params.entry.url ?? ''}`.trim());
    }
  });
  const send = (method, params = {}) => new Promise((resolve) => {
    pending.set(++id, resolve);
    ws.send(JSON.stringify({ id, method, params }));
  });
  const evaluate = async (expression) => (await send('Runtime.evaluate',
    { expression, awaitPromise: true, returnByValue: true, userGesture: true })).result?.result?.value;
  const load = async (query, width, height) => {
    await send('Emulation.setDeviceMetricsOverride', { width, height, deviceScaleFactor: 1, mobile: width < 500 });
    await send('Page.navigate', { url: `http://127.0.0.1:${httpPort}/${query}` });
    await sleep(1000);
  };
  const shot = async (name) => {
    const { result } = await send('Page.captureScreenshot', { format: 'png' });
    writeFileSync(path.join(outDir, name), Buffer.from(result.data, 'base64'));
  };
  await send('Runtime.enable');
  await send('Log.enable');
  await send('Page.enable');

  const r = {};
  await load('?pressed=E4,G4', 1280, 720);
  r.keys = await evaluate(`document.querySelectorAll('button[data-note]').length`);
  r.whiteKeys = await evaluate(`[...document.querySelectorAll('button[data-note]')].filter((b) => !b.dataset.note.includes('#')).length`);
  r.pressed = await evaluate(`[...document.querySelectorAll('button[data-note].is-active')].map((b) => b.dataset.note).join(',')`);
  await shot('desktop.png');
  for (const [w, h] of [[1280, 720], [390, 844], [360, 740]]) {
    await load('?pressed=E4,G4', w, h);
    r[`overflowX${w}`] = await evaluate(`document.documentElement.scrollWidth - document.documentElement.clientWidth`);
    if (w === 390) await shot('mobile.png');
  }

  await load('', 1280, 720);
  r.clickC5 = await evaluate(`(async () => {
    const k = document.querySelector('[data-note="C5"]'); k.click();
    await new Promise((r) => setTimeout(r, 120)); return k.classList.contains('is-active'); })()`);
  await sleep(800);
  await send('Input.dispatchKeyEvent', { type: 'keyDown', key: 'd', code: 'KeyD', text: 'd', windowsVirtualKeyCode: 68 });
  await send('Input.dispatchKeyEvent', { type: 'keyUp', key: 'd', code: 'KeyD', windowsVirtualKeyCode: 68 });
  r.keyD = await evaluate(`new Promise((r) => setTimeout(() => r([...document.querySelectorAll('.is-active')].map((b) => b.dataset.note).join(',')), 120))`);
  await sleep(800);

  // Playback: every visible strike, as an is-active addition or an animation start on a key.
  r.playback = await evaluate(`(async () => {
    const lit = [], animated = [], events = [];
    let frame = 0, ticking = true;
    const tick = () => { frame++; if (ticking) requestAnimationFrame(tick); };
    requestAnimationFrame(tick);
    const keys = [...document.querySelectorAll('button[data-note]')];
    const btn = [...document.querySelectorAll('button')].find((b) => /play/i.test(b.textContent));
    const obs = new MutationObserver((ms) => { for (const m of ms) {
      const was = (m.oldValue || '').split(/\\s+/).includes('is-active'), is = m.target.classList.contains('is-active');
      if (is && !was) lit.push(m.target.dataset.note);
      if (is !== was) events.push([m.target.dataset.note, is, frame]);
    } });
    obs.observe(document.body, { subtree: true, attributes: true, attributeFilter: ['class'], attributeOldValue: true });
    for (const k of keys) k.addEventListener('animationstart', () => animated.push(k.dataset.note));
    btn.click();
    await new Promise((r) => setTimeout(r, 150));
    const disabledWhilePlaying = btn.disabled;
    const t = performance.now();
    while (btn.disabled && performance.now() - t < 20000) await new Promise((r) => setTimeout(r, 100));
    obs.disconnect();
    ticking = false;
    // For each re-lit key: animation frames between its off and the next on (0 = never painted dark).
    const repeatFrames = [];
    events.forEach(([note, on, f], i) => {
      if (!on) return;
      const off = events.slice(0, i).reverse().find(([n, o]) => n === note && !o);
      const prevOn = events.slice(0, i).reverse().find(([, o]) => o);
      if (off && prevOn && prevOn[0] === note) repeatFrames.push(note + ':' + (f - off[2]));
    });
    return { disabledWhilePlaying, enabledAfter: !btn.disabled, lit: lit.join(' '), litCount: lit.length,
             animatedCount: animated.length, animated: animated.join(' '), repeatFrames: repeatFrames.join(' ') };
  })()`);
  r.consoleProblems = problems;
  console.log(JSON.stringify(r, null, 2));
} finally {
  chrome.kill();
  server.kill();
  await sleep(300);
  rmSync(profile, { recursive: true, force: true });
}
