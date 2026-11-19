'use strict';

const { spawn } = require('child_process');

const workspaceRoot = process.env.WORKSPACE_ROOT || '/app/code';
const buildTimeoutMs = Number(process.env.PRODUCTION_BUILD_TIMEOUT_MS || 120000);
const child = spawn('npm', ['run', 'build'], {
  cwd: workspaceRoot,
  env: process.env,
  stdio: ['ignore', 'pipe', 'pipe'],
  detached: true,
});

let output = '';
let finished = false;
let successAfterTimeout = false;
let timeout;

function finish(code) {
  if (finished) return;
  finished = true;
  clearTimeout(timeout);
  process.exitCode = code;
}

function terminate(signal) {
  try {
    process.kill(-child.pid, signal);
  } catch (error) {
    child.kill(signal);
  }
}

child.stdout.on('data', chunk => {
  output += chunk.toString();
  process.stdout.write(chunk);
});
child.stderr.on('data', chunk => {
  output += chunk.toString();
  process.stderr.write(chunk);
});
child.on('error', error => {
  process.stderr.write(`${error.stack || error}\n`);
  finish(1);
});
child.on('close', code => {
  if (successAfterTimeout) return finish(0);
  finish(code === 0 ? 0 : (code || 1));
});

timeout = setTimeout(() => {
  const buildCompleted = /Build complete\./.test(output) && !/Build failed with errors\./.test(output);
  if (!buildCompleted) {
    terminate('SIGKILL');
    return finish(124);
  }

  successAfterTimeout = true;
  terminate('SIGTERM');
  setTimeout(() => {
    if (!finished) {
      terminate('SIGKILL');
      finish(0);
    }
  }, 2000);
}, buildTimeoutMs);
