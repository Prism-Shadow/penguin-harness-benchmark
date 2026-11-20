import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import { pathToFileURL } from 'node:url';
import { debugSession } from '../../environment/debug_session.mjs';
import { sourceContainer } from '../../environment/source_container.mjs';

const directory = await fs.mkdtemp(path.join(os.tmpdir(), 'source-announcement-'));
try {
  const events = [];
  const cdp = {};
  const container = await sourceContainer(events, { cdp });
  const session = await debugSession({ container, cdp });
  const pause = () => new Promise(resolve => setTimeout(resolve, 30));
  let scriptId = 0;
  const add = url => session.discover({ url, scriptId: String(++scriptId),
    executionContextId: 1, startLine: 0, startColumn: 0, endLine: 1, endColumn: 0,
    hash: '', scriptLanguage: 'JavaScript' }, 'console.log(1)');
  const remote = await add('https://unmapped.invalid/remote.js');
  const evaluated = await add('');
  await pause();
  assert.equal(events.length, 0, 'unmapped and evaluated sources are lazy');
  const filename = path.join(directory, 'local.js');
  await fs.writeFile(filename, 'console.log(1)');
  await add(pathToFileURL(filename).href);
  for (let attempt = 0; events.length === 0 && attempt < 30; attempt++) await pause();
  assert.equal(events.length, 1);
  assert.equal(events[0].reason, 'new');
  assert.equal(events[0].source.path, filename);
  await remote.toDap();
  await evaluated.toDap();
  await pause();
  assert.equal(events.length, 3);
  assert.equal(new Set(events.map(event => event.source.sourceReference)).size, 3);
  await remote.toDap();
  await evaluated.toDap();
  await container.loadedSources();
  await pause();
  assert.equal(events.length, 3, 'each source is announced once');
  await session.dispose();
} finally {
  await fs.rm(directory, { recursive: true, force: true });
}
