const assert = require('node:assert/strict');
const { test } = require('node:test');
const { startFacadeProcess } = require('./native/environment/facade_bridge');

function launch(source, onLine = () => {}, timeoutMs = 2000) {
  const stdio = `const console = {
    log(value) { require('node:fs').writeSync(1, String(value) + '\\n'); },
    error(value) { require('node:fs').writeSync(2, String(value) + '\\n'); }
  };`;
  return startFacadeProcess(process.execPath, ['-e', stdio + source], { env: process.env, onLine, timeoutMs });
}

test('supervisor completes four asynchronous stdin/stdout handshakes', async () => {
  let count = 0;
  const worker = startFacadeProcess('/bin/bash', ['-c', `
    for index in 0 1 2 3; do
      printf 'READY %s\\n' "$index"
      IFS= read -r actual || exit 2
      test "$actual" = "NATIVE $index" || exit 3
    done
    printf 'FACADE_OK\\n'
  `], { env: process.env, timeoutMs: 2000, onLine(line) {
    if (line === 'FACADE_OK') assert.equal(count, 4);
    else {
      assert.equal(line, 'READY ' + count);
      worker.child.stdin.write('NATIVE ' + count++ + '\n');
    }
  } });
  await worker.completion;
  assert.equal(count, 4);
  assert.equal(worker.child.exitCode, 0);
});

test('a completion marker cannot hide a later failing exit', async () => {
  const worker = launch("console.log('FACADE_OK'); console.error('assertion after marker'); process.exitCode = 7;");
  await assert.rejects(worker.completion, error => error.message.includes('exit: 7') && error.message.includes('assertion after marker'));
});

test('assertion failure reaps a child that ignores SIGTERM', async () => {
  const worker = launch("process.on('SIGTERM', () => {}); setInterval(() => {}, 1000); console.log('READY');", () => {
    throw new Error('native payload mismatch');
  });
  await assert.rejects(worker.completion, /native payload mismatch/);
  assert.equal(worker.child.signalCode, 'SIGKILL');
  assert.throws(() => process.kill(worker.child.pid, 0), { code: 'ESRCH' });
});

test('timeouts retain the last callback stage and forcibly reap the worker', async () => {
  const worker = launch("process.on('SIGTERM', () => {}); setInterval(() => {}, 1000); console.log('waiting-for-native-1');", () => {}, 1000);
  await assert.rejects(worker.completion, error => error.message.includes('Facade round trip timeout') && error.message.includes('waiting-for-native-1'));
  assert.equal(worker.child.signalCode, 'SIGKILL');
  assert.throws(() => process.kill(worker.child.pid, 0), { code: 'ESRCH' });
});

test('asynchronous native promise rejection follows the same cleanup path', async () => {
  const worker = launch("setInterval(() => {}, 1000); console.log('READY');", () => {
    Promise.reject(new Error('native error')).catch(worker.fail);
  });
  await assert.rejects(worker.completion, /native error/);
  assert.equal(worker.child.signalCode, 'SIGKILL');
});

test('missing executable preserves launch error without waiting for timeout', async () => {
  const worker = startFacadeProcess('/nonexistent/facade-runtime', [], { env: process.env, onLine() {}, timeoutMs: 2000 });
  await assert.rejects(worker.completion, { code: 'ENOENT' });
});
