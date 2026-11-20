import {assert, path, readFile, root, mod, fromRepo, req, productionModule,
  setupBrowser, params, runProbe} from '../support.mjs';

await runProbe('1007', async () => {
  const RequestParams = await req();
  const Config = (await mod('src/js/lib/config.js')).default;
  const d = Config.getDefault();
  assert.ok(Object.hasOwn(d, 'htmlCaptureCssImage'));
  assert.ok(Object.hasOwn(d, 'htmlCaptureWebFont'));
  assert.equal(Object.hasOwn(d, 'saveCssImage'), false);
});
