import assert from 'node:assert/strict';

const streamGlobals = [
  'ReadableStream', 'WritableStream', 'TransformStream',
  'ByteLengthQueuingStrategy', 'CountQueuingStrategy',
  'TextEncoder', 'TextDecoder', 'TextEncoderStream', 'TextDecoderStream',
];

async function beforeDeadline(promise) {
  let timer;
  try {
    return await Promise.race([
      promise,
      new Promise((_, reject) => {
        timer = setTimeout(() => reject(new Error('stream callback made no progress')), 2000);
      }),
    ]);
  } finally {
    clearTimeout(timer);
  }
}

export async function runFetchStreamProfiles(loadProduction, profiles = ['native', 'native-no-encoder', 'codec-free']) {
  const saved = new Map([...streamGlobals, 'fetch', 'Headers', 'Response', 'CS'].map(
    name => [name, Object.getOwnPropertyDescriptor(globalThis, name)],
  ));
  const restore = () => {
    for (const [name, descriptor] of saved) {
      if (descriptor) Object.defineProperty(globalThis, name, descriptor);
      else delete globalThis[name];
    }
  };
  try {
    for (const profile of profiles) {
      restore();
      if (profile === 'codec-free') {
        for (const name of streamGlobals) delete globalThis[name];
      } else if (profile === 'native-no-encoder') {
        delete globalThis.TextEncoder;
      }
      delete globalThis.fetch;
      let callbacks;
      globalThis.CS = { LLMAgent: { HttpBridge: {
        SendStreamRequestAsync(_url, _method, _headers, body, header, chunk, complete) {
          assert.equal(JSON.parse(body).stream, true);
          callbacks = { header, chunk, complete };
        },
        SendRequestAsync() { assert.fail('stream request used the buffered bridge'); },
      } } };
      await loadProduction('unity/agent_proj/src/polyfills/streams-polyfill.mts');
      await loadProduction('unity/agent_proj/src/polyfills/fetch-polyfill.mts');
      const open = async () => {
        callbacks = undefined;
        const pending = fetch('http://probe.invalid/v1', {
          method: 'POST', body: JSON.stringify({ stream: true }),
        });
        assert.ok(callbacks, 'fetch did not enter the production streaming bridge');
        callbacks.header(JSON.stringify({ status: 200, headers: { 'content-type': 'text/event-stream' } }));
        const response = await beforeDeadline(pending);
        return response.body.pipeThrough(new TextDecoderStream()).getReader();
      };
      const reader = await open();
      for (const text of [`prefix-${process.pid}-`, '中文-🚀-tail']) {
        callbacks.chunk('');
        const reading = reader.read();
        callbacks.chunk(text);
        assert.deepEqual(await beforeDeadline(reading), { value: text, done: false });
      }
      callbacks.complete('{}');
      assert.equal((await beforeDeadline(reader.read())).done, true);
      const failed = await open();
      const rejected = assert.rejects(beforeDeadline(failed.read()), /bridge-disconnected/);
      callbacks.complete(JSON.stringify({ error: 'bridge-disconnected' }));
      await rejected;
      console.log(`production fetch stream profile passed: ${profile}`);
    }
  } finally {
    restore();
  }
}
