import {assert, path, readFile, root, mod, fromRepo, req, productionModule,
  setupBrowser, params, runProbe} from '../support.mjs';

await runProbe('1017', async () => {
  const RequestParams = await req();
  const Snapshot = (await mod('src/js/snapshot/snapshot.js')).default;
  const text = await Snapshot.take({nodeType: 3, nodeName: '#text', data: '<unsafe>'}, {ignoreHiddenElement: false});
  assert.equal(text.needEscape, true);
});
