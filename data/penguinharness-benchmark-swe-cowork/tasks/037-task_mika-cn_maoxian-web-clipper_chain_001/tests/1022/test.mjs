import {assert, path, readFile, root, mod, fromRepo, req, productionModule,
  setupBrowser, params, runProbe} from '../support.mjs';

await runProbe('1022', async () => {
  const RequestParams = await req();
  const {ExtMsg} = await setupBrowser();
  const CaptureTool = (await mod('src/js/capturer/tool.js')).default;
  assert.equal(CaptureTool.isFilterMatch('<images>', 'data:image/png;base64,AA=='), true);
  ExtMsg.clearMocks();
});
