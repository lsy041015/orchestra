import { mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';

const cwd = process.cwd();
writeFileSync(join(cwd, 'argv.json'), JSON.stringify(process.argv.slice(2)));
writeFileSync(join(cwd, 'stdin.txt'), readFileSync(0, 'utf8'));

if (process.env.FAKE_MODE === 'fail') {
  process.stderr.write('boom\n');
  process.exitCode = 3;
} else if (process.env.FAKE_MODE === 'api-error') {
  // Shape of a real Codex 0.156 API rejection: the message is pretty-printed JSON.
  const message = JSON.stringify({ type: 'error', error: { code: 'unsupported_value',
    message: "Unsupported value: 'minimal' is not supported with the 'gpt-6-luna' model." },
  status: 400 }, null, 2);
  for (const event of [
    { type: 'thread.started', thread_id: 't-123' },
    { type: 'error', message },
    { type: 'turn.failed', error: { message } },
  ]) process.stdout.write(`${JSON.stringify(event)}\n`);
  process.exitCode = 1;
} else if (process.env.FAKE_MODE === 'retry-error') {
  // A transient stream error that Codex recovers from within the same turn.
  for (const event of [
    { type: 'thread.started', thread_id: 't-123' },
    { type: 'error', message: 'stream disconnected - retrying sampling request (1/5 in 200ms)...' },
    { type: 'item.completed', item: { type: 'agent_message', text: 'Status: DONE\nChanged files: a.txt' } },
    { type: 'turn.completed' },
  ]) process.stdout.write(`${JSON.stringify(event)}\n`);
} else if (process.env.FAKE_MODE === 'retry-then-crash') {
  // A recovered stream error, then a crash explained only on stderr.
  for (const event of [
    { type: 'thread.started', thread_id: 't-123' },
    { type: 'error', message: 'stream disconnected - retrying sampling request (1/5 in 200ms)...' },
    { type: 'item.completed', item: { type: 'reasoning', text: 'Reading the brief.' } },
  ]) process.stdout.write(`${JSON.stringify(event)}\n`);
  process.stderr.write('sandbox setup failed\n');
  process.exitCode = 101;
} else if (process.env.FAKE_MODE === 'no-status') {
  for (const event of [
    { type: 'thread.started', thread_id: 't-123' },
    { type: 'item.completed', item: { type: 'agent_message', text: 'Which file should I change?' } },
    { type: 'turn.completed' },
  ]) process.stdout.write(`${JSON.stringify(event)}\n`);
} else if (process.env.FAKE_MODE === 'hang') {
  // A long run that only a signal ends.
  writeFileSync(join(cwd, 'pid.txt'), String(process.pid));
  setInterval(() => {}, 1000);
} else if (process.env.FAKE_MODE === 'event-fail') {
  for (const event of [
    { type: 'thread.started', thread_id: 't-123' },
    { type: 'item.completed', item: { type: 'agent_message', text: 'Status: DONE' } },
    { type: 'turn.failed' },
  ]) process.stdout.write(`${JSON.stringify(event)}\n`);
} else {
  if (process.env.FAKE_MODE === 'touch') {
    writeFileSync(join(cwd, 'a.txt'), 'a\n');
    writeFileSync(join(cwd, 'b.txt'), 'b\n');
  } else if (process.env.FAKE_MODE === 'break-git') {
    // An out-of-scope edit, then a repository git can no longer read.
    writeFileSync(join(cwd, 'b.txt'), 'b\n');
    writeFileSync(join(cwd, '.git', 'HEAD'), 'garbage\n');
  } else if (process.env.FAKE_MODE === 'nested') {
    writeFileSync(join(cwd, 'a.txt'), 'a\n');
    mkdirSync(join(cwd, 'out', 'deep'), { recursive: true });
    writeFileSync(join(cwd, 'out', 'deep', 'c.txt'), 'c\n');
  }
  for (const event of [
    { type: 'thread.started', thread_id: 't-123' },
    { type: 'item.completed', item: { type: 'agent_message', text: 'Status: DONE\nChanged files: a.txt' } },
    { type: 'turn.completed' },
  ]) process.stdout.write(`${JSON.stringify(event)}\n`);
}
