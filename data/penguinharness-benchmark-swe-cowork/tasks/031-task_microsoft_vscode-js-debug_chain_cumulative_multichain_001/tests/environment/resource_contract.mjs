import assert from 'node:assert/strict';
import http from 'node:http';
import { resourceProvider } from './contract_runtime.mjs';

export async function checkResource({ chunks = [], headers, expected, directStatus = 500,
  resourceStatus = 200, networkFailure = false, success = true, closeFailure = false,
  offsets = [], noCdp = false, noResource = false, noStream = false, legacy = false }) {
  const reads = [];
  const closes = [];
  const requests = [];
  const server = http.createServer((_request, response) => {
    response.writeHead(directStatus);
    response.end('direct-body');
  });
  await new Promise((resolve, reject) => {
    server.once('error', reject);
    server.listen(0, '127.0.0.1', resolve);
  });
  let provider;
  try {
    const url = `http://127.0.0.1:${server.address().port}/map?identity=one`;
    provider = await resourceProvider(noCdp ? undefined : {
      Network: {
        enable: async () => ({}),
        getCookies: async () => ({ cookies: [] }),
        loadNetworkResource: async request => {
          requests.push(request);
          if (networkFailure) throw new Error('network boundary failure');
          if (noResource) return undefined;
          return { resource: { success, httpStatusCode: resourceStatus, headers,
            stream: noStream ? undefined : 'owned-stream' } };
        },
      },
      IO: {
        read: async request => {
          reads.push(request.offset);
          assert.equal(request.handle, 'owned-stream');
          assert.ok(reads.length <= chunks.length, 'unexpected trailing read');
          const chunk = chunks[reads.length - 1];
          if (chunk instanceof Error) throw chunk;
          return chunk;
        },
        close: async request => {
          await new Promise(resolve => setImmediate(resolve));
          closes.push(request.handle);
          if (closeFailure) throw new Error('close boundary failure');
        },
      },
    }, legacy);
    const response = await provider.fetch(url);
    const usesBrowser = directStatus >= 400 && !noCdp;
    assert.equal(requests.length, usesBrowser ? 1 : 0);
    if (usesBrowser) {
      assert.equal(requests[0].url, url);
      assert.equal(requests[0].options.includeCredentials, true);
    }
    assert.equal(response.url, url);
    assert.deepEqual(reads, offsets);
    const acquired = usesBrowser && !networkFailure && !noResource && !noStream;
    assert.deepEqual(closes, acquired ? ['owned-stream'] : []);
    if (expected === undefined) {
      assert.equal(response.ok, false);
      assert.equal(response.statusCode, directStatus);
      assert.equal(response.body, 'direct-body');
    } else {
      assert.equal(response.ok, true);
      assert.equal(response.statusCode, directStatus < 400 ? directStatus : resourceStatus);
      assert.equal(response.body, expected);
    }
  } finally {
    provider?.dispose();
    await new Promise(resolve => server.close(resolve));
  }
}
