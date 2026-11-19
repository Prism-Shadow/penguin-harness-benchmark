import {assert, path, readFile, root, mod, fromRepo, req, productionModule,
  setupBrowser, params, runProbe} from '../support.mjs';

await runProbe('1031', async () => {
  const RequestParams = await req();
  const Config = (await mod('src/js/lib/config.js')).default;
  const d = Config.getDefault();
  assert.equal(Object.hasOwn(d, 'htmlCustomBodyBgCssEnabled'), true);
  assert.equal(Object.hasOwn(d, 'customBodyBgCssEnabled'), false);
});
