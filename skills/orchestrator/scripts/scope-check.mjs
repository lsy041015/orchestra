#!/usr/bin/env node
// Reports files a worker changed outside its allowed list. codex-worker.mjs
// runs this check around every Codex run. For a Claude worker, the main
// session records a baseline before dispatch and checks it before review:
//   node scope-check.mjs before --cwd <project> --state <file>
//   node scope-check.mjs after --cwd <project> --state <file> --allowed <list>
import { lstatSync, readFileSync, realpathSync, writeFileSync } from 'node:fs';
import { devNull, homedir } from 'node:os';
import path from 'node:path';
import { spawn } from 'node:child_process';
import { fileURLToPath } from 'node:url';

// cmd.exe and CreateProcess search the current directory before PATH, so a
// git.exe inside the project would run instead of the real tool.
if (process.platform === 'win32') process.env.NoDefaultCurrentDirectoryInExePath = '1';

// Resolves { output } or { error: <first stderr line> }.
function git(cwd, args) {
  return new Promise((resolve) => {
    // No optional locks: a background status must not make the user's own git
    // commands fail on index.lock.
    // A worker can write .git/config in a nested repo it created, and this
    // runs outside its sandbox: switch off the config keys that execute commands.
    const child = spawn('git', ['-c', 'core.fsmonitor=false', '-c', `core.hooksPath=${devNull}`,
      '-c', 'core.untrackedCache=false', '-C', cwd, ...args],
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

// True when dir is the home directory or one of its parents. dir must be a
// physical path.
export function holdsHome(dir) {
  let home = homedir();
  try { home = realpathSync(home); } catch {}
  const rel = path.relative(dir, home);
  return !(rel === '..' || rel.startsWith(`..${path.sep}`) || path.isAbsolute(rel));
}

// git status prints paths from the repository root, not from cwd, so the
// allowed list is converted to root-relative paths. A trailing slash marks a
// directory whose whole subtree is allowed. cwd must be a physical path.
export async function repoScope(cwd, allowed) {
  const result = await git(cwd, ['rev-parse', '--show-cdup']);
  if (result.error) return result;
  const root = path.resolve(cwd, result.output.trim());
  // Every app's cache under $HOME is untracked there, so the check would
  // list only noise, after seconds per hundred thousand files.
  if (holdsHome(root)) return { error: `the repository root ${root} holds the home directory; git init the project` };
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

export async function snapshot(root) {
  // No rename detection: a rename's old path must count as a change too.
  // --ignored: a worker's .env, dist/ or node_modules/ is invisible otherwise.
  const result = await git(root, ['status', '--porcelain=v1', '-z', '-uall', '--no-renames',
    '--ignored=matching']);
  if (result.error) return result;
  const files = new Map();
  for (const entry of result.output.split('\0')) {
    if (entry.length < 4) continue;
    const file = entry.slice(3);
    const normalized = file.replace(/\\/g, '/');
    // The orchestra workspace (ledger, briefs, this state file) is written by
    // the main session, not the worker.
    if (entry.startsWith('!!') && /^\.orchestra(\/|$)/.test(normalized)) continue;
    let hash = 'deleted';
    let stat;
    try {
      // Size and change times, not content: hashing read every untracked
      // file, and a checkout at $HOME (950k files, 145 GB) never finished.
      // ponytail: a same-size edit within one timestamp tick is missed on
      // coarse-clock filesystems (FAT: 2 s); hash small files if that matters.
      stat = lstatSync(path.resolve(root, file));
      hash = `${stat.size}:${stat.mtimeMs}:${stat.ctimeMs}`;
    } catch (error) {
      // Keep an unreadable entry instead of aborting the run.
      hash = error.code === 'ENOENT' ? 'deleted' : error.code;
    }
    // An ignored directory is one entry: its own mtime catches files added or
    // removed directly in it. ponytail: edits deeper down are missed.
    if (stat?.isDirectory() && !entry.startsWith('!!')) {
      hash = 'directory';
      // A submodule or an untracked nested repository shows up as one
      // directory, so its own status is merged in under that path, and its
      // HEAD stands for the directory to catch commits made inside it.
      const dir = path.resolve(root, file);
      const top = await git(dir, ['rev-parse', '--show-cdup']);
      const inner = !top.error && !top.output.trim() && await snapshot(dir);
      if (inner && !inner.error) {
        hash = `HEAD ${inner.head}`;
        const prefix = normalized.replace(/\/?$/, '/');
        for (const [name, value] of inner.files) files.set(prefix + name, value);
      }
    }
    files.set(normalized, hash);
  }
  // A file committed during the run is clean again, so HEAD is recorded too.
  const head = await git(root, ['rev-parse', '--verify', '--quiet', 'HEAD']);
  return { head: head.error ? null : head.output.trim(), files };
}

// The text after "Scope: ".
export async function compare(repo, before, after) {
  if (before.error) return `unchecked (git: ${before.error})`;
  if (after.error) return `unchecked (git status failed after the run: ${after.error})`;
  const changed = new Set([...before.files.keys(), ...after.files.keys()]
    .filter((file) => before.files.get(file) !== after.files.get(file)));
  if (before.head !== after.head) {
    const committed = !after.head ? { error: 'HEAD is missing after the run' }
      : await git(repo.root, before.head ? ['diff-tree', '-r', '--name-only', '-z', before.head, after.head]
        : ['ls-tree', '-r', '--name-only', '-z', after.head]);
    if (committed.error) return `unchecked (git: ${committed.error})`;
    for (const file of committed.output.split('\0')) if (file) changed.add(file);
  }
  const outside = [...changed].filter((file) => !repo.allows(file)).sort();
  return outside.length ? `outside allowed: ${outside.join(', ')}` : 'ok';
}

async function cli(args) {
  const [command, ...rest] = args;
  const values = {};
  for (let i = 0; i < rest.length; i += 2) {
    const flag = rest[i];
    if (!['--cwd', '--state', '--allowed'].includes(flag) || values[flag] !== undefined ||
        i + 1 === rest.length) {
      throw new Error(`Invalid argument: ${flag}`);
    }
    values[flag] = rest[i + 1];
  }
  const required = { before: ['--cwd', '--state'], after: ['--cwd', '--state', '--allowed'] }[command];
  if (!required) throw new Error('Usage: scope-check.mjs before|after --cwd <dir> --state <file> [--allowed <list>]');
  for (const flag of required) {
    if (values[flag] === undefined) throw new Error(`Missing required argument: ${flag}`);
  }
  const cwd = realpathSync(path.resolve(values['--cwd']));
  const allowed = (values['--allowed'] ?? '').split(',').map((item) => item.trim()).filter(Boolean);
  if (command === 'after' && !allowed.length) throw new Error('Invalid --allowed');

  const repo = await repoScope(cwd, allowed);
  if (command === 'before') {
    const base = repo.error ? repo : await snapshot(repo.root);
    writeFileSync(values['--state'], JSON.stringify(base.error ? { error: base.error }
      : { root: repo.root, head: base.head, files: Object.fromEntries(base.files) }));
    process.stdout.write(base.error ? `Scope: unchecked (git: ${base.error})\n` : 'Scope: baseline recorded\n');
    return base.error ? 1 : 0;
  }

  const saved = JSON.parse(readFileSync(values['--state'], 'utf8'));
  let scope;
  if (!saved.error && !repo.error && saved.root !== repo.root) {
    scope = `unchecked (the baseline is for ${saved.root})`;
  } else {
    const before = saved.error ? saved : repo.error ? repo
      : { head: saved.head, files: new Map(Object.entries(saved.files)) };
    const after = before.error ? before : await snapshot(repo.root);
    scope = await compare(repo, before, after);
  }
  process.stdout.write(`Scope: ${scope}\n`);
  return scope === 'ok' ? 0 : 1;
}

if (process.argv[1] && realpathSync(process.argv[1]) === fileURLToPath(import.meta.url)) {
  cli(process.argv.slice(2)).then((code) => { process.exitCode = code; }, (error) => {
    process.stderr.write(`${error.message}\n`);
    process.exitCode = 2;
  });
}
