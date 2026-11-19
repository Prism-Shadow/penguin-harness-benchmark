import {assert, path, readFile, root, mod, fromRepo, req, productionModule,
  setupBrowser, params, runProbe} from '../support.mjs';

await runProbe('1006', async () => {
  const RequestParams = await req();
  const Config = (await mod('src/js/lib/config.js')).default;
  const d = Config.getDefault();
  assert.equal(d.htmlCaptureAudio, 'remove');
  assert.equal(d.htmlCaptureVideo, 'remove');
  assert.equal(d.htmlEmbedFilter, '<images>');
});
