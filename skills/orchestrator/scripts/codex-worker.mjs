#!/usr/bin/env node
import { existsSync, readFileSync, realpathSync, statSync } from 'node:fs';
import { homedir } from 'node:os';
import path from 'node:path';
import { spawn, spawnSync } from 'node:child_process';
import { compare, holdsHome, repoScope, snapshot } from './scope-check.mjs';

// cmd.exe and CreateProcess search the current directory before PATH, so a
// codex.cmd or git.exe inside the project would run instead of the real tool.
if (process.platform === 'win32') process.env.NoDefaultCurrentDirectoryInExePath = '1';

const efforts = new Set(['none', 'minimal', 'low', 'medium', 'high', 'xhigh', 'max', 'ultra']);
const flags = new Set(['--model', '--effort', '--cwd', '--brief', '--allowed', '--resume']);

function parseArgs(args) {
  const values = {};
  for (let i = 0; i < args.length; i++) {
    const flag = args[i];
    if (!flags.has(flag) || values[flag] !== undefined || i + 1 === args.length) {
      throw new Error(`Invalid argument: ${flag}`);
    }
    values[flag] = args[++i];
  }
  for (const flag of ['--model', '--effort', '--cwd', '--brief', '--allowed']) {
    if (values[flag] === undefined) throw new Error(`Missing required argument: ${flag}`);
  }
  if (!/^[A-Za-z0-9][A-Za-z0-9._-]*$/.test(values['--model'])) throw new Error('Invalid --model');
  if (!efforts.has(values['--effort'])) throw new Error('Invalid --effort');
  if (values['--resume'] !== undefined && !/^[A-Za-z0-9][A-Za-z0-9-]*$/.test(values['--resume'])) {
    throw new Error('Invalid --resume');
  }

  let cwd = path.resolve(values['--cwd']);
  let brief = path.resolve(values['--brief']);
  if (!existsSync(cwd) || !statSync(cwd).isDirectory()) throw new Error('Invalid --cwd');
  if (!existsSync(brief) || !statSync(brief).isFile()) throw new Error('Invalid --brief');
  // Physical paths, as git sees them: through a linked --cwd, git finds the
  // link target's repository while the link path would place the root elsewhere.
  cwd = realpathSync(cwd);
  brief = realpathSync(brief);
  // The sandbox writes anywhere inside --cwd: at or above $HOME that includes
  // ~/.ssh, shell profiles and every agent's config.
  if (holdsHome(cwd)) {
    throw new Error('Invalid --cwd: it holds the home directory, where the Codex sandbox could write anywhere; git init the project and use its root');
  }
  // The Codex sandbox writes only inside --cwd, and the report lives next to the brief.
  const inside = path.relative(cwd, brief);
  if (inside === '..' || inside.startsWith(`..${path.sep}`) || path.isAbsolute(inside)) {
    throw new Error('Invalid --brief: it must be inside --cwd, where the Codex sandbox can write the report');
  }
  const allowed = values['--allowed'].split(',').map((item) => item.trim()).filter(Boolean);
  if (!allowed.length) throw new Error('Invalid --allowed');
  return { model: values['--model'], effort: values['--effort'], cwd, brief, allowed,
    resume: values['--resume'] };
}

// Codex caches the efforts each model supports. The API has accepted an
// unlisted pair (gpt-6-luna + ultra) without saying which level ran.
function cachedEfforts(model) {
  try {
    const home = process.env.CODEX_HOME || path.join(homedir(), '.codex');
    const { models } = JSON.parse(readFileSync(path.join(home, 'models_cache.json'), 'utf8'));
    const levels = models.find((entry) => entry?.slug === model)?.supported_reasoning_levels;
    return Array.isArray(levels) ? levels.map((level) => level?.effort ?? level) : undefined;
  } catch {
    return undefined;
  }
}

// 110 minutes: under the 2 hour limit of the Bash background run that starts
// this worker, so the BLOCKED report still prints. ORCHESTRA_CODEX_TIMEOUT_MS
// overrides it; above 2^31 - 1 ms setTimeout would fire at once.
function timeoutMs() {
  const value = Number(process.env.ORCHESTRA_CODEX_TIMEOUT_MS);
  return Number.isInteger(value) && value > 0 ? Math.min(value, 2 ** 31 - 1) : 110 * 60 * 1000;
}

// The codex shim runs the native binary as its own child, which holds this
// worker's stdout: killing only the shim leaves Codex running and the pipe open.
// ponytail: without a working `ps` only the direct child is killed.
function killTree(pid) {
  if (process.platform === 'win32') {
    spawnSync('taskkill', ['/pid', String(pid), '/t', '/f'], { stdio: 'ignore', windowsHide: true });
    return;
  }
  const children = new Map();
  const ps = spawnSync('ps', ['-A', '-o', 'pid=', '-o', 'ppid='], { encoding: 'utf8' });
  for (const line of (ps.stdout || '').split('\n')) {
    const [child, parent] = line.trim().split(/\s+/).map(Number);
    if (child) children.set(parent, [...(children.get(parent) ?? []), child]);
  }
  const tree = [pid];
  for (let i = 0; i < tree.length; i++) tree.push(...(children.get(tree[i]) ?? []));
  for (const each of tree) {
    try { process.kill(each, 'SIGKILL'); } catch {}
  }
}

function spawnCodex(args, cwd, prompt) {
  const injected = process.env.ORCHESTRA_CODEX_BIN !== undefined;
  // Windows needs a shell for codex.cmd. Every arg is validated and space-free,
  // so one joined string is safe and avoids Node's DEP0190 warning.
  const viaShell = !injected && process.platform === 'win32';
  const command = injected ? process.execPath : viaShell ? `codex ${args.join(' ')}` : 'codex';
  const commandArgs = injected ? [process.env.ORCHESTRA_CODEX_BIN, ...args] : viaShell ? [] : args;
  return new Promise((resolve) => {
    const child = spawn(command, commandArgs, {
      cwd,
      shell: viaShell,
      windowsHide: true,
      stdio: ['pipe', 'pipe', 'pipe'],
    });
    let stdout = '';
    let partial = '';
    let stderr = '';
    let error;
    let timedOut = false;
    // Only a few event types are read (parseEvents), so any other line shrinks
    // to a marker: a long --json stream then costs no memory. It still counts
    // as progress after an error.
    const keep = /thread\.started|agent_message|turn\.failed|"error"/;
    child.stdout.setEncoding('utf8').on('data', (chunk) => {
      const lines = (partial + chunk).split('\n');
      partial = lines.pop();
      for (const line of lines) stdout += `${keep.test(line) ? line : '{"type":"progress"}'}\n`;
    });
    // Only the tail of stderr is reported.
    child.stderr.setEncoding('utf8').on('data', (chunk) => { stderr = (stderr + chunk).slice(-65536); });
    // Pass a stop request on (the codex shim forwards it to the native binary).
    // Five seconds later the whole tree is killed and the pipes are closed, so
    // stopping this worker never leaves Codex editing files and a child that
    // ignores the signal never strands the worker before its report.
    let killer;
    const stop = (signal) => {
      // Windows has no signal to pass on: cmd.exe would die and leave codex.exe.
      if (process.platform === 'win32') killTree(child.pid);
      else child.kill(signal);
      killer ??= setTimeout(() => {
        killTree(child.pid);
        child.stdout.destroy();
        child.stderr.destroy();
      }, 5000);
    };
    const signals = ['SIGINT', 'SIGTERM', 'SIGHUP'];
    for (const signal of signals) process.on(signal, stop);
    // A hung Codex (network stall, a prompt nobody answers) must end as BLOCKED.
    const timer = setTimeout(() => {
      timedOut = true;
      stop('SIGTERM');
    }, timeoutMs());
    child.stdin.on('error', () => {});
    child.on('error', (cause) => { error = cause; });
    child.on('close', (code, signal) => {
      clearTimeout(timer);
      clearTimeout(killer);
      for (const name of signals) process.off(name, stop);
      resolve({ stdout: stdout + partial, stderr, code, signal, error, timedOut });
    });
    child.stdin.end(prompt);
  });
}

// Codex wraps API rejections (unknown model, unsupported effort) as a
// pretty-printed JSON string; keep only the human-readable message.
function apiMessage(text) {
  try {
    const parsed = JSON.parse(text);
    return parsed.error?.message || parsed.message || text;
  } catch {
    return text;
  }
}

function parseEvents(stdout) {
  let thread = 'unknown';
  let message;
  let failed = false;
  let failure;
  for (const line of stdout.split(/\r?\n/)) {
    try {
      const event = JSON.parse(line);
      if (event.type === 'thread.started' && typeof event.thread_id === 'string') {
        thread = event.thread_id;
      } else if (event.type === 'turn.failed' || event.type === 'error') {
        // Codex also reports stream retries it recovers from as `error`; only a
        // failed turn or exit fails the run. The text still explains a failure.
        if (event.type === 'turn.failed') failed = true;
        failure = apiMessage(typeof event.error === 'string' ? event.error :
          event.error?.message || event.message || event.item?.error?.message) || failure;
      } else {
        // Progress after an error means Codex recovered from it.
        failure = undefined;
        if (event.type === 'item.completed' && event.item?.type === 'agent_message') {
          message = typeof event.item.text === 'string' ? event.item.text : '';
        }
      }
    } catch {}
  }
  return { thread, message, failed, failure };
}

function failureText(stderr, error, code, signal, failed, hasMessage) {
  const tail = stderr.trimEnd().split(/\r?\n/).slice(-20).join('\n');
  return tail || error?.message ||
    (failed ? 'Codex reported a failure' : signal ? `Codex terminated by signal ${signal}` :
      code === 0 && !hasMessage ? 'Codex returned no agent_message' : `Codex exited with code ${code}`);
}

async function main() {
  let options;
  try {
    options = parseArgs(process.argv.slice(2));
  } catch (error) {
    process.stderr.write(`${error.message}\n`);
    process.exitCode = 2;
    return;
  }

  let prompt;
  try {
    prompt = readFileSync(options.brief, 'utf8');
  } catch (error) {
    process.stderr.write(`Cannot read --brief: ${error.message}\n`);
    process.exitCode = 2;
    return;
  }

  const listed = cachedEfforts(options.model);
  if (listed && !listed.includes(options.effort)) {
    process.stdout.write(`Status: BLOCKED\nUnresolved: ${options.model} does not support effort ` +
      `${options.effort} (Codex lists: ${listed.join(', ')})\nCodex thread: none\n` +
      'Scope: unchecked (Codex did not run)\n');
    process.exitCode = 1;
    return;
  }

  const repo = await repoScope(options.cwd, options.allowed);
  const before = repo.error ? repo : await snapshot(repo.root);
  const args = ['exec'];
  if (options.resume) args.push('resume', options.resume);
  args.push('--json', '-m', options.model, '-c', `model_reasoning_effort=${options.effort}`);
  if (options.resume) args.push('-c', 'sandbox_mode=workspace-write');
  else args.push('-s', 'workspace-write');
  // Opt-in: the sandbox blocks even loopback sockets (ROS 2/DDS, localhost servers, installs).
  if (process.env.ORCHESTRA_CODEX_NETWORK === '1') args.push('-c', 'sandbox_workspace_write.network_access=true');
  // The brief is the whole job: the user's Codex plugins (another Superpowers,
  // for one) would add skills and hooks with their own workflow.
  args.push('--disable', 'plugins', '--skip-git-repo-check', '-');

  const run = await spawnCodex(args, options.cwd, prompt);
  const events = parseEvents(run.stdout);
  const after = before.error ? before : await snapshot(repo.root);
  const scope = await compare(repo, before, after);

  let reason;
  if (run.timedOut) {
    reason = `Codex timed out after ${Math.round(timeoutMs() / 1000)} s and was stopped`;
  } else if (run.code !== 0 || events.failed || events.message === undefined) {
    reason = events.failure ||
      failureText(run.stderr, run.error, run.code, run.signal, events.failed, events.message !== undefined);
  } else if (!/^Status: /m.test(events.message)) {
    reason = `Codex reply has no status block: ${events.message.trim().split(/\r?\n/)[0].slice(0, 200)}`;
  }
  const first = reason === undefined ? events.message : `Status: BLOCKED\nUnresolved: ${reason}`;
  process.stdout.write(`${first}\nCodex thread: ${events.thread}\nScope: ${scope}\n`);
  if (reason !== undefined) process.exitCode = 1;
}

main().catch((error) => {
  process.stderr.write(`${error.message}\n`);
  process.exitCode = 1;
});
