#!/usr/bin/env node
import { createHash } from 'node:crypto';
import { existsSync, readFileSync, statSync } from 'node:fs';
import path from 'node:path';
import { spawn } from 'node:child_process';

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
  if (!/^[A-Za-z0-9._-]+$/.test(values['--model'])) throw new Error('Invalid --model');
  if (!efforts.has(values['--effort'])) throw new Error('Invalid --effort');
  if (values['--resume'] !== undefined && !/^[A-Za-z0-9-]+$/.test(values['--resume'])) {
    throw new Error('Invalid --resume');
  }

  const cwd = path.resolve(values['--cwd']);
  const brief = path.resolve(values['--brief']);
  if (!existsSync(cwd) || !statSync(cwd).isDirectory()) throw new Error('Invalid --cwd');
  if (!existsSync(brief) || !statSync(brief).isFile()) throw new Error('Invalid --brief');
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

// Resolves { output } or { error: <first stderr line> }.
function git(cwd, args) {
  return new Promise((resolve) => {
    // No optional locks: a background status must not make the user's own git
    // commands fail on index.lock.
    const child = spawn('git', ['-C', cwd, ...args],
      { windowsHide: true, env: { ...process.env, GIT_OPTIONAL_LOCKS: '0' } });
    const chunks = [];
    let stderr = '';
    child.stdout.on('data', (chunk) => chunks.push(chunk));
    child.stderr.setEncoding('utf8').on('data', (chunk) => { stderr += chunk; });
    child.on('error', (error) => resolve({ error: error.message }));
    child.on('close', (code) => resolve(code === 0 ? { output: Buffer.concat(chunks).toString('utf8') }
      : { error: stderr.trim().split(/\r?\n/)[0] || `git exited with code ${code}` }));
  });
}

// git status prints paths from the repository root, not from --cwd, so the
// allowed list is converted to root-relative paths. A trailing slash marks a
// directory whose whole subtree is allowed.
async function repoScope(cwd, allowed) {
  const result = await git(cwd, ['rev-parse', '--show-cdup']);
  if (result.error) return result;
  const root = path.resolve(cwd, result.output.trim());
  const files = new Set();
  const dirs = [];
  for (const item of allowed) {
    const rel = path.relative(root, path.resolve(cwd, item.replace(/[\\/]/g, path.sep)))
      .replace(/\\/g, '/');
    if (/[\\/]$/.test(item)) dirs.push(rel ? `${rel}/` : '');
    else files.add(rel);
  }
  return { root, allows: (file) => files.has(file) || dirs.some((dir) => file.startsWith(dir)) };
}

async function snapshot(root) {
  const result = await git(root, ['status', '--porcelain=v1', '-z', '-uall']);
  if (result.error) return result;
  const fields = result.output.split('\0');
  const files = new Map();
  for (let i = 0; i < fields.length; i++) {
    const entry = fields[i];
    if (entry.length < 4) continue;
    const status = entry.slice(0, 2);
    const file = entry.slice(3);
    const normalized = file.replace(/\\/g, '/');
    let hash = 'deleted';
    try {
      hash = createHash('sha1').update(readFileSync(path.resolve(root, file))).digest('hex');
    } catch (error) {
      // Submodules show up as directories (EISDIR); keep the entry instead of aborting the run.
      hash = error.code === 'ENOENT' ? 'deleted' : error.code;
    }
    files.set(normalized, hash);
    if (status.includes('R') || status.includes('C')) i++;
  }
  return { files };
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
    let stderr = '';
    let error;
    child.stdout.setEncoding('utf8').on('data', (chunk) => { stdout += chunk; });
    child.stderr.setEncoding('utf8').on('data', (chunk) => { stderr += chunk; });
    child.stdin.on('error', () => {});
    child.on('error', (cause) => { error = cause; });
    child.on('close', (code, signal) => resolve({ stdout, stderr, code, signal, error }));
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
      } else if (event.type === 'item.completed' && event.item?.type === 'agent_message') {
        message = typeof event.item.text === 'string' ? event.item.text : '';
      } else if (event.type === 'turn.failed' || event.type === 'error') {
        // Codex also reports stream retries it recovers from as `error`; only a
        // failed turn or exit fails the run. The text still explains a failure.
        if (event.type === 'turn.failed') failed = true;
        failure = apiMessage(typeof event.error === 'string' ? event.error :
          event.error?.message || event.message || event.item?.error?.message) || failure;
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

  const repo = await repoScope(options.cwd, options.allowed);
  const before = repo.error ? repo : await snapshot(repo.root);
  const args = ['exec'];
  if (options.resume) args.push('resume', options.resume);
  args.push('--json', '-m', options.model, '-c', `model_reasoning_effort=${options.effort}`);
  if (options.resume) args.push('-c', 'sandbox_mode=workspace-write');
  else args.push('-s', 'workspace-write');
  // Opt-in: the sandbox blocks even loopback sockets (ROS 2/DDS, localhost servers, installs).
  if (process.env.ORCHESTRA_CODEX_NETWORK === '1') args.push('-c', 'sandbox_workspace_write.network_access=true');
  args.push('--skip-git-repo-check', '-');

  const run = await spawnCodex(args, options.cwd, prompt);
  const events = parseEvents(run.stdout);
  const after = before.error ? before : await snapshot(repo.root);
  let scope;
  if (before.error) {
    scope = `unchecked (git: ${before.error})`;
  } else if (after.error) {
    scope = `unchecked (git status failed after the run: ${after.error})`;
  } else {
    const outside = Array.from(new Set([...before.files.keys(), ...after.files.keys()]))
      .filter((file) => before.files.get(file) !== after.files.get(file) && !repo.allows(file))
      .sort();
    scope = outside.length ? `outside allowed: ${outside.join(', ')}` : 'ok';
  }

  let reason;
  if (run.code !== 0 || events.failed || events.message === undefined) {
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
