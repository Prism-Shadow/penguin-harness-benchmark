const assert = require('node:assert/strict');
const { createRequire } = require('node:module');
const path = require('node:path');

const requireFromRepo = createRequire(path.join(process.env.REPO_ROOT, 'package.json'));
requireFromRepo('reflect-metadata');
requireFromRepo('inversify');
const dataUriToBuffer = requireFromRepo('data-uri-to-buffer');
assert.equal(dataUriToBuffer('data:text/plain;base64,w6k=').toString('utf8'), 'é');
assert.equal(requireFromRepo('source-map/package.json').version, '0.8.0-beta.0');
for (const name of ['@types/estraverse/package.json', 'tsx',
  '@jridgewell/trace-mapping', '@jridgewell/gen-mapping']) requireFromRepo.resolve(name);
console.log('isolated baseline dependency preflight passed');
