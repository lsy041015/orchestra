#!/usr/bin/env node
// Reports files a worker changed outside its allowed list. codex-worker.mjs
// runs this check around every Codex run. For a Claude worker, the main
// session records a baseline before dispatch and checks it before review:
//   node scope-check.mjs before --cwd <project> --state <file>
//   node scope-check.mjs after --cwd <project> --state <file> --allowed <list>
import { createHash } from 'node:crypto';
import { lstatSync, readdirSync, readFileSync, realpathSync, writeFileSync } from 'node:fs';
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
    // `./` or `src/..//` is the whole repository: every path would be allowed.
    if (!rel) throw new Error(`Invalid --allowed: ${item} is the repository root; list files or subdirectories`);
    if (/[\\/]$/.test(item)) dirs.push(`${rel}/`);
    else files.add(rel);
  }
  // The slash lets `sub/` also cover the entry `sub` itself (a submodule).
  return { root, allows: (file) => files.has(file) || dirs.some((dir) => `${file}/`.startsWith(dir)) };
}

// The paths to hash, as { file, ignored }. The top level uses git status,
// which lists only what differs from HEAD; its config and attributes are the
// user's own, which the user's git status runs anyway. A nested repository
// may be the worker's: git status there reads file contents through its
// filter drivers, so a `filter.<x>.clean` in its .git/config would run on the
// host. ls-files reads only the index and the ignore rules, never a file.
async function entries(root, nested) {
  if (!nested) {
    // No rename detection: a rename's old path must count as a change too.
    // --ignored: a worker's .env, dist/ or node_modules/ is invisible otherwise.
    // --ignore-submodules=all: otherwise status looks inside each submodule,
    // through that submodule's filter drivers, and a `submodule.<x>.ignore` or
    // `diff.ignoreSubmodules` setting hides edits there.
    const result = await git(root, ['status', '--porcelain=v1', '-z', '-uall', '--no-renames',
      '--ignored=matching', '--ignore-submodules=all']);
    if (result.error) return result;
    // Status also skips files flagged assume-unchanged (a lowercase tag) or
    // skip-worktree (S), which anyone can set with git update-index, so those
    // and every submodule (mode 160000) are hashed on every run.
    const index = await git(root, ['ls-files', '-z', '-s', '-v']);
    if (index.error) return index;
    const always = index.output.split('\0')
      .filter((entry) => /^([a-z]|S) /.test(entry) || entry.slice(2).startsWith('160000 '))
      .map((entry) => ({ file: entry.slice(entry.indexOf('\t') + 1), ignored: false }));
    return { list: [...result.output.split('\0').filter((entry) => entry.length >= 4)
      .map((entry) => ({ file: entry.slice(3), ignored: entry.startsWith('!!') })), ...always] };
  }
  const listed = await git(root, ['ls-files', '-z', '--cached', '--others', '--exclude-standard']);
  if (listed.error) return listed;
  const ignored = await git(root, ['ls-files', '-z', '--others', '--ignored', '--exclude-standard',
    '--directory']);
  if (ignored.error) return ignored;
  const split = (output) => output.split('\0').filter(Boolean);
  // A submodule's .git is a file naming its git directory: repointing it swaps
  // the index and ignore rules this listing trusts, so it is hashed too.
  let gitfile = false;
  try { gitfile = lstatSync(path.join(root, '.git')).isFile(); } catch {}
  return { list: [...split(listed.output).map((file) => ({ file, ignored: false })),
    ...split(ignored.output).map((file) => ({ file, ignored: true })),
    ...(gitfile ? [{ file: '.git', ignored: false }] : [])] };
}

// One hash over the names, sizes and change times of a directory's direct
// entries.
function listing(dir) {
  const digest = createHash('sha1');
  try {
    for (const name of readdirSync(dir).sort()) {
      try {
        const stat = lstatSync(path.join(dir, name));
        digest.update(`${name}\0${stat.size}:${stat.mtimeMs}:${stat.ctimeMs}\0`);
      } catch {}
    }
  } catch (error) {
    return error.code;
  }
  return digest.digest('hex');
}

export async function snapshot(root, nested = false) {
  const result = await entries(root, nested);
  if (result.error) return result;
  const files = new Map();
  for (const { file, ignored } of result.list) {
    const normalized = file.replace(/\\/g, '/');
    // An unmerged path is listed once per stage; a submodule may be listed twice.
    if (files.has(normalized)) continue;
    // The orchestra workspace (ledger, briefs, this state file) is written by
    // the main session, not the worker.
    if (ignored && /^\.orchestra(\/|$)/.test(normalized)) continue;
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
    // An ignored directory is one entry: its direct entries catch files added,
    // removed or rewritten right in it. ponytail: edits deeper down are missed;
    // walk the tree if a cache dir ever needs more than that.
    if (stat?.isDirectory() && ignored) hash = listing(path.resolve(root, file));
    if (stat?.isDirectory() && !ignored) {
      hash = 'directory';
      // A submodule or an untracked nested repository shows up as one
      // directory, so its own files are merged in under that path, and its
      // HEAD stands for the directory to catch commits made inside it.
      const dir = path.resolve(root, file);
      const top = await git(dir, ['rev-parse', '--show-cdup']);
      // Not readable (dubious ownership, a .git file pointing nowhere): its
      // files are unseen, so the run is unchecked rather than ok.
      if (top.error) return { error: `nested repository ${normalized}: ${top.error}` };
      if (!top.output.trim()) {
        const inner = await snapshot(dir, true);
        if (inner.error) return { error: `nested repository ${normalized}: ${inner.error}` };
        hash = `HEAD ${inner.head}`;
        const prefix = normalized.replace(/\/?$/, '/');
        for (const [name, value] of inner.files) files.set(prefix + name, value);
      }
    }
    // The mark lets compare() label the entry for the reviewer.
    files.set(normalized, ignored ? `!! ${hash}` : hash);
  }
  // git status never lists the git directory, but a hook, or an alias or
  // core.sshCommand in its config, runs on the user's next git command.
  // ponytail: a nested repository's own git directory is not covered.
  if (!nested) {
    const dirs = await git(root, ['rev-parse', '--git-dir', '--git-common-dir']);
    if (dirs.error) return dirs;
    const [own, common] = dirs.output.trim().split(/\r?\n/).map((dir) => path.resolve(root, dir));
    // Not all of info/: git gc writes info/refs there.
    for (const [target, slash] of [[path.join(common, 'config'), ''], [path.join(own, 'config.worktree'), ''],
      [path.join(common, 'hooks'), '/'], [path.join(common, 'info/attributes'), ''],
      [path.join(common, 'info/exclude'), '']]) {
      let hash;
      try {
        const stat = lstatSync(target);
        hash = stat.isDirectory() ? listing(target) : `${stat.size}:${stat.mtimeMs}:${stat.ctimeMs}`;
      } catch (error) {
        hash = error.code === 'ENOENT' ? 'deleted' : error.code;
      }
      files.set(path.relative(root, target).replace(/\\/g, '/') + slash, hash);
    }
  }
  // A file committed during the run is clean again, so HEAD is recorded too.
  const head = await git(root, ['rev-parse', '--verify', '--quiet', 'HEAD']);
  return { head: head.error ? null : head.output.trim(), files };
}

// File names, and the nested repository an unchecked reason names, are the
// worker's, and the Scope line is the one the reader trusts: a line break or
// other control character could start a forged `Scope: ok` line, and
// thousands of names would make one huge line.
const NOT_PLAIN = /[\u0000-\u001f\u007f-\u009f\u2028\u2029\ufeff]/g;
const plain = (text) => text.replace(NOT_PLAIN, (c) => `\\u${c.charCodeAt(0).toString(16).padStart(4, '0')}`);
const MAX_LISTED = 50;

// The text after "Scope: ".
export async function compare(repo, before, after) {
  return plain(await describe(repo, before, after));
}

async function describe(repo, before, after) {
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
  // Caches the task's own commands write (__pycache__/, build/) are gitignored,
  // so the label lets the reviewer tell them from a stray .env.
  const ignored = (file) => [before.files.get(file), after.files.get(file)]
    .some((hash) => hash?.startsWith('!! '));
  const outside = [...changed].filter((file) => !repo.allows(file)).sort()
    .map((file) => (ignored(file) ? `${file} (ignored)` : file));
  if (!outside.length) return 'ok';
  const more = outside.length - MAX_LISTED;
  return `outside allowed: ${outside.slice(0, MAX_LISTED).join(', ')}${more > 0 ? `, and ${more} more` : ''}`;
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
    process.stdout.write(base.error ? `Scope: unchecked (git: ${plain(base.error)})\n` : 'Scope: baseline recorded\n');
    return base.error ? 1 : 0;
  }

  const saved = JSON.parse(readFileSync(values['--state'], 'utf8'));
  let scope;
  if (!saved.error && !repo.error && saved.root !== repo.root) {
    scope = plain(`unchecked (the baseline is for ${saved.root})`);
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
