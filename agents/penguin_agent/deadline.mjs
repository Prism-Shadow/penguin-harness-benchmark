// Optional absolute deadline for tasks that expose a countdown to the agent.
// This supervisor and the task's timer read the same timestamp. Installation and
// server startup happen before it starts. SIGINT asks `penguin run` to abort the
// server-side task; cleanup allowance is separate from the research deadline.
import { spawn } from 'node:child_process';
import { mkdirSync, renameSync, writeFileSync } from 'node:fs';
import { dirname } from 'node:path';

const [deadlineFile, receiptFile, secondsText, graceText, command, ...args] = process.argv.slice(2);
const seconds = Number(secondsText);
const grace = Number(graceText);
if (!command || !deadlineFile?.startsWith('/') || !receiptFile?.startsWith('/') ||
    !Number.isInteger(seconds) || seconds <= 0 || !Number.isInteger(grace) || grace < 0) {
  console.error('deadline: expected absolute deadline/receipt paths, positive seconds, nonnegative grace, command');
  process.exit(2);
}
function atomic(path, value) {
  mkdirSync(dirname(path), { recursive: true });
  const tmp = `${path}.${process.pid}.tmp`;
  writeFileSync(tmp, `${JSON.stringify(value)}\n`, { mode: 0o644 });
  renameSync(tmp, path);
}
const startedAt = Date.now();
const deadlineAt = startedAt + seconds * 1000;
const state = { started_at_ms: startedAt, deadline_ms: deadlineAt, timeout_sec: seconds, timed_out: false };
atomic(deadlineFile, state);
let killTimer;
let finished = false;
const child = spawn(command, args, { stdio: 'inherit', detached: true });
function signal(sig) {
  if (child.pid && !finished) {
    try { process.kill(-child.pid, sig); } catch (err) { if (err.code !== 'ESRCH') throw err; }
  }
}
const timer = setTimeout(() => {
  state.timed_out = true;
  state.abort_requested_at_ms = Date.now();
  signal('SIGINT');
  killTimer = setTimeout(() => signal('SIGKILL'), grace * 1000);
}, Math.max(0, deadlineAt - Date.now()));
child.on('error', (err) => {
  finished = true;
  clearTimeout(timer);
  clearTimeout(killTimer);
  atomic(receiptFile, { ...state, error: err.message, finished_at_ms: Date.now() });
  process.exitCode = 3;
});
child.on('exit', (code, sig) => {
  finished = true;
  clearTimeout(timer);
  clearTimeout(killTimer);
  atomic(receiptFile, { ...state, child_exit_code: code, child_signal: sig, finished_at_ms: Date.now() });
  // A planned deadline is not an infrastructure error. run.sh stops the server
  // and collects costs/traces next, including when the CLI needed SIGKILL.
  process.exitCode = state.timed_out ? 0 : (code ?? 3);
});
for (const sig of ['SIGTERM', 'SIGINT']) process.on(sig, () => signal(sig));
