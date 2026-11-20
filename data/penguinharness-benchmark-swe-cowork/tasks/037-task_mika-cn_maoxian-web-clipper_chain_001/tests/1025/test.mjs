import {assert, path, readFile, root, mod, fromRepo, req, productionModule,
  setupBrowser, params, runProbe} from '../support.mjs';

await runProbe('1025', async () => {
  const RequestParams = await req();
  const Config = (await mod('src/js/lib/config.js')).default;
  assert.equal(Config.getDefault().htmlWebFontFilterList, 'woff2|woff|otf|ttf');
});
