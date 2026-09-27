#!/usr/bin/env node
import { createHash } from 'node:crypto';
import { existsSync, readFileSync, statSync } from 'node:fs';
import path from 'node:path';
import { spawn } from 'node:child_process';

const efforts = new Set(['none', 'minimal', 'low', 'medium', 'high', 'xhigh', 'max']);
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
  const allowed = values['--allowed'].split(',').map((item) => item.trim()).filter(Boolean);
  if (!allowed.length) throw new Error('Invalid --allowed');
  return { model: values['--model'], effort: values['--effort'], cwd, brief,
    allowed: new Set(allowed.map((item) => path.relative(cwd,
      path.resolve(cwd, item.replace(/[\\/]/g, path.sep))).replace(/\\/g, '/'))),
    resume: values['--resume'] };
}

function gitStatus(cwd) {
  return new Promise((resolve) => {
    const child = spawn('git', ['-C', cwd, 'status', '--porcelain=v1', '-z', '-uall'],
      { windowsHide: true });
    const chunks = [];
    child.stdout.on('data', (chunk) => chunks.push(chunk));
    child.on('error', () => resolve(null));
    child.on('close', (code) => resolve(code === 0 ? Buffer.concat(chunks) : null));
  });
}

async function snapshot(cwd) {
  const output = await gitStatus(cwd);
  if (output === null) return null;
  const fields = output.toString('utf8').split('\0');
  const files = new Map();
  for (let i = 0; i < fields.length; i++) {
    const entry = fields[i];
    if (entry.length < 4) continue;
    const status = entry.slice(0, 2);
    const file = entry.slice(3);
    const normalized = file.replace(/\\/g, '/');
    let hash = 'deleted';
    try {
      hash = createHash('sha1').update(readFileSync(path.resolve(cwd, file))).digest('hex');
    } catch (error) {
      // Submodules show up as directories (EISDIR); keep the entry instead of aborting the run.
      hash = error.code === 'ENOENT' ? 'deleted' : error.code;
    }
    files.set(normalized, hash);
    if (status.includes('R') || status.includes('C')) i++;
  }
  return files;
}

function spawnCodex(args, cwd, prompt) {
  const injected = process.env.RELAY_CODEX_BIN !== undefined;
  // Windows needs a shell for codex.cmd. Every arg is validated and space-free,
  // so one joined string is safe and avoids Node's DEP0190 warning.
  const viaShell = !injected && process.platform === 'win32';
  const command = injected ? process.execPath : viaShell ? `codex ${args.join(' ')}` : 'codex';
  const commandArgs = injected ? [process.env.RELAY_CODEX_BIN, ...args] : viaShell ? [] : args;
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

function parseEvents(stdout) {
  let thread = 'unknown';
  let message;
  let hasMessage = false;
  let failure;
  let hasFailure = false;
  for (const line of stdout.split(/\r?\n/)) {
    try {
      const event = JSON.parse(line);
      if (event.type === 'thread.started' && typeof event.thread_id === 'string') {
        thread = event.thread_id;
      } else if (event.type === 'item.completed' && event.item?.type === 'agent_message') {
        message = typeof event.item.text === 'string' ? event.item.text : '';
        hasMessage = true;
      } else if (event.type === 'turn.failed' || event.type === 'error') {
        hasFailure = true;
        failure = typeof event.error === 'string' ? event.error :
          event.error?.message || event.message || event.item?.error?.message;
      }
    } catch {}
  }
  return { thread, message, hasMessage, failure, hasFailure };
}

function failureText(stderr, error, code, signal, hasFailure, hasMessage) {
  const tail = stderr.trimEnd().split(/\r?\n/).slice(-20).join('\n');
  return tail || error?.message ||
    (hasFailure ? 'Codex reported a failure' : signal ? `Codex terminated by signal ${signal}` :
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

  const before = await snapshot(options.cwd);
  const args = ['exec'];
  if (options.resume) args.push('resume', options.resume);
  args.push('--json', '-m', options.model, '-c', `model_reasoning_effort=${options.effort}`);
  if (options.resume) args.push('-c', 'sandbox_mode=workspace-write');
  else args.push('-s', 'workspace-write');
  args.push('--skip-git-repo-check', '-');

  const run = await spawnCodex(args, options.cwd, prompt);
  const events = parseEvents(run.stdout);
  const after = before === null ? null : await snapshot(options.cwd);
  const outside = after === null ? [] : Array.from(new Set([...before.keys(), ...after.keys()]))
    .filter((file) => before.get(file) !== after.get(file) && !options.allowed.has(file))
    .sort();
  const scope = before === null ? 'unchecked (not a git repo)' :
    (outside.length ? `outside allowed: ${outside.join(', ')}` : 'ok');
  const failed = run.code !== 0 || events.hasFailure || !events.hasMessage;
  const first = failed ? `Status: BLOCKED\nUnresolved: ${events.failure ||
    failureText(run.stderr, run.error, run.code, run.signal, events.hasFailure, events.hasMessage)}` : events.message;
  process.stdout.write(`${first}\nCodex thread: ${events.thread}\nScope: ${scope}\n`);
  if (failed) process.exitCode = 1;
}

main().catch((error) => {
  process.stderr.write(`${error.message}\n`);
  process.exitCode = 1;
});
