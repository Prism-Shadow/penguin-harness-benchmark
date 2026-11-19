import {assert, path, readFile, root, mod, fromRepo, req, productionModule,
  setupBrowser, params, runProbe} from '../support.mjs';

await runProbe('1018', async () => {
  const RequestParams = await req();
  const Config = (await mod('src/js/lib/config.js')).default;
  const d = Config.getDefault();
  assert.equal(d.htmlCaptureEmbed, 'saveImage');
  assert.equal(d.htmlCaptureObject, 'saveImage');
});
