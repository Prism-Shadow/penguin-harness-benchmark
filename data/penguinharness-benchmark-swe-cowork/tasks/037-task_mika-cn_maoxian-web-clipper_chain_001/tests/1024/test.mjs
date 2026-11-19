import {assert, path, readFile, root, mod, fromRepo, req, productionModule,
  setupBrowser, params, runProbe} from '../support.mjs';

await runProbe('1024', async () => {
  const RequestParams = await req();
  const {ExtMsg} = await setupBrowser();
  const CaptureTool = (await mod('src/js/capturer/tool.js')).default;
  assert.equal(typeof CaptureTool.matchFilterList, 'function');
  const items = [{url: 'https://a.org/a.woff'}, {url: 'https://a.org/b.otf'}];
  const flags = CaptureTool.matchFilterList('woff|otf', items, () => [false, false]);
  assert.deepEqual(flags, [true, false]);
  ExtMsg.clearMocks();
});
