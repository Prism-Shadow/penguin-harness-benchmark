const assert = require('node:assert/strict');
const childProcess = require('node:child_process');
const crypto = require('node:crypto');
const path = require('node:path');
const readline = require('node:readline');
const harness = require('./probe_harness');
const { guardShellCompletion } = require('./shell_contract');

function startFacadeProcess(command, args, { env, onLine, timeoutMs = 45000 }) {
  const child = childProcess.spawn(command, args, { env, stdio: ['pipe', 'pipe', 'pipe'] });
  let failure;
  let output = '';
  const fail = error => {
    failure ||= error;
    if (child.exitCode === null && child.signalCode === null) child.kill('SIGKILL');
  };
  const lines = readline.createInterface({ input: child.stdout });
  lines.on('line', line => {
    output = (output + line + '\n').slice(-8192);
    try { onLine(line); }
    catch (error) { fail(error); }
  });
  child.stderr.on('data', data => {
    output = (output + data).slice(-8192);
    process.stderr.write(data);
  });
  child.stdin.on('error', fail);
  child.on('error', fail);
  const timer = setTimeout(() => fail(new Error('Facade round trip timeout')), timeoutMs);
  const completion = new Promise((resolve, reject) => {
    child.on('close', (code, signal) => {
      clearTimeout(timer);
      lines.close();
      if (!failure && code !== 0) failure = new Error(`Public facade process exit: ${code}, signal: ${signal}`);
      if (failure) {
        failure.message += '\nFacade process output:\n' + output;
        reject(failure);
      } else resolve();
    });
  });
  return { child, completion, fail };
}

function deployedDock(directory) {
  const restore = harness.installMocks();
  try {
    const socket = new harness.Socket();
    const original = process.cwd();
    process.chdir(directory);
    try {
      global.__startHost = true;
      require(path.join(directory, 'main.js'));
      global.__electron.app.emit('ready');
      assert(global.__hostBridge, 'deployed main starts its bridge');
      global.__hostBridge.emit('connection', socket);
    } finally {
      delete global.__startHost;
      process.chdir(original);
    }
    for (const badge of ['deployed-17', '', 'another-value']) {
      socket.emit('dock-setBadge', badge);
      socket.emit('dock-getBadge');
      assert.equal(global.__electron.app.dock.badge, badge);
      assert.equal(socket.out.filter(event => event.name === 'dock-getBadge-completed').at(-1)?.args[0], badge);
    }
    socket.emit('dock-bounce', 'critical');
    assert.equal(socket.out.find(event => event.name === 'dock-bounce-completed')?.args[0], 17);
  } finally { restore(); }
}

async function bridge(assembly, name) {
  let socketIo;
  try { socketIo = require('/opt/probe-node/node_modules/socket.io'); }
  catch (error) { console.error('Pinned Socket.IO dependency unavailable:', error.message); process.exitCode = 78; return; }
  const server = require('node:http').createServer();
  const transport = socketIo(server);
  const restore = harness.installMocks();
  const nonce = crypto.randomBytes(8).toString('hex');
  const pending = new Map();
  const nativeCalls = [];
  let worker;
  let finished = false;
  const fail = error => worker.fail(error);
  function defer(label, reject) {
    nativeCalls.push(label);
    return new Promise((resolve, rejectPromise) => {
      pending.set(label, () => reject ? rejectPromise(new Error(reject)) : resolve());
      worker.child.stdin.write('NATIVE ' + label + '\n');
    });
  }
  global.__electron.shell.openExternal = (url, options) => {
    const index = nativeCalls.length;
    assert.equal(url, `https://external.invalid/${nonce}/${index}`);
    if (index % 2) assert.deepEqual(options, { activate: false, workingDirectory: `/workspace/${nonce}` });
    else assert.equal(options, undefined);
    return defer(`shell-${index}`, index % 2 ? `denied-${nonce}-${index}` : null);
  };
  const shellContract = guardShellCompletion(global.__electron.shell);
  const originalWindow = global.__electron.BrowserWindow;
  global.__electron.BrowserWindow = class extends originalWindow {
    constructor(options) {
      super(options);
      this.webContents.loadURL = (url, received) => {
        if (url === `https://initial.invalid/${nonce}`) return Promise.resolve();
        const index = nativeCalls.length;
        assert.equal(url, `https://post.invalid/${nonce}/${index}`);
        assert.equal(received.extraHeaders, 'X-Probe: ' + nonce);
        if (index < 2) {
          assert.equal(received.postData.length, 3);
          assert.equal(received.postData[0].type, 'rawData');
          assert(Buffer.isBuffer(received.postData[0].bytes));
          assert.deepEqual(received.postData[0].bytes, Buffer.from([0, 255, 128, 7 + index]));
          assert.deepEqual(received.postData[1], { type: 'file', filePath: `/uploads/${nonce}`, offset: 17 + index, length: -1, modificationTime: 123.5 + index });
          assert.deepEqual(received.postData[2], { type: 'blob', blobUUID: nonce + '-' + index });
        } else if (index === 2) assert.deepEqual(received.postData, []);
        else assert(received.postData == null);
        return defer(`post-${index}`, index === 1 ? 'load-denied-' + nonce : null);
      };
    }
  };
  transport.on('connection', socket => {
    shellContract.observe(socket);
    try { harness.loadHost(socket); }
    catch (error) { fail(error); }
  });
  process.on('unhandledRejection', fail);
  try {
    await new Promise((resolve, reject) => {
      server.once('error', reject);
      server.listen(0, 'localhost', resolve);
    });
    worker = startFacadeProcess(process.env.PROBE_DOTNET || 'dotnet', [assembly], {
      env: { ...process.env, PROBE_CASE: name, PROBE_SOCKET_PORT: String(server.address().port), PROBE_NONCE: nonce },
      onLine(line) {
        if (line.startsWith('RELEASE ')) {
          const label = line.slice(8);
          assert(pending.has(label), 'Settlement requested only after native invocation');
          pending.get(label)();
          pending.delete(label);
        } else if (line === 'FACADE_OK') finished = true;
        else process.stdout.write(line + '\n');
      },
    });
    await worker.completion;
    assert(finished, 'Public facade verified results');
    assert.equal(nativeCalls.length, 4, 'Every operation reached native Electron boundary exactly once');
    assert.equal(pending.size, 0);
    shellContract.verify();
    console.log('Real production facade / Socket.IO / production main / native boundary round trip passed:', name);
  } finally {
    if (worker && worker.child.exitCode === null && worker.child.signalCode === null) {
      worker.fail(new Error('Facade bridge shutting down'));
      await worker.completion.catch(() => {});
    }
    restore();
    process.removeListener('unhandledRejection', fail);
    await new Promise((resolve, reject) => {
      const timer = setTimeout(() => reject(new Error('Socket.IO cleanup timeout')), 2000);
      transport.close(() => { clearTimeout(timer); resolve(); });
      server.closeAllConnections();
    });
  }
}

if (require.main === module) {
  const [first, second] = process.argv.slice(2);
  Promise.resolve().then(() => first === 'deployed-dock' ? deployedDock(second) : bridge(first, second))
    .catch(error => { console.error(error); process.exitCode = 1; });
}
module.exports = { deployedDock, startFacadeProcess };
