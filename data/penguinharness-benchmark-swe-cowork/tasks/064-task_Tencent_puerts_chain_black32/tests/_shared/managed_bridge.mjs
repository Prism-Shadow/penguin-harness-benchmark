import { spawn } from 'node:child_process';
import { createInterface } from 'node:readline';
import assert from 'node:assert/strict';

export function managedBridge() {
  assert.ok(process.env.PUERTS_MANAGED_BRIDGE, 'managed integration command is required');
  const [executable, ...args] = JSON.parse(process.env.PUERTS_MANAGED_BRIDGE);
  const child = spawn(executable, args, { stdio: ['pipe', 'pipe', 'pipe'] });
  const pending = new Map();
  let sequence = 0;
  let callbacks;
  let failure;
  let diagnostic = '';
  const fail = error => {
    failure = error;
    for (const entry of pending.values()) { clearTimeout(entry.timer); entry.reject(error); }
    pending.clear();
  };
  child.stderr.on('data', bytes => { diagnostic += bytes.toString(); });
  child.on('error', fail);
  child.on('exit', code => {
    if (code !== 0 || pending.size) fail(new Error(`managed bridge exited ${code}: ${diagnostic}`));
  });
  const lines = createInterface({ input: child.stdout });
  lines.on('line', line => {
    try {
      const event = JSON.parse(line);
      if (event.kind === 'ack') {
        const entry = pending.get(event.id);
        assert.ok(entry, 'unexpected managed acknowledgement');
        pending.delete(event.id); clearTimeout(entry.timer); entry.resolve();
      } else {
        assert.ok(callbacks, 'managed callback without active request');
        if (event.kind === 'header' || event.kind === 'chunk') assert.equal(event.done, false, 'callback buffered to EOF');
        callbacks[event.kind](event.text);
      }
    } catch (error) { fail(error); }
  });
  const send = command => {
    if (failure) return Promise.reject(failure);
    return new Promise((resolve, reject) => {
      const id = ++sequence;
      const timer = setTimeout(() => { pending.delete(id); reject(new Error(`managed ${command.action} timed out: ${diagnostic}`)); }, 5000);
      pending.set(id, { resolve, reject, timer });
      child.stdin.write(JSON.stringify({ ...command, id }) + '\n');
    });
  };
  return {
    send,
    start(url, method, headers, body, header, chunk, complete) {
      callbacks = { header, chunk, complete };
      return send({ action: 'start', url, method, headers, body });
    },
    chunk(text) { return send({ action: 'chunk', bytes: Buffer.from(text).toString('base64') }); },
    async close() {
      child.stdin.end();
      await new Promise(resolve => {
        if (child.exitCode !== null) return resolve();
        const timer = setTimeout(() => { child.kill(); resolve(); }, 1000);
        child.once('exit', () => { clearTimeout(timer); resolve(); });
      });
      lines.close();
      if (failure) throw failure;
    },
  };
}
