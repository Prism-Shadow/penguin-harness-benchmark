import {assert, path, readFile, root, mod, fromRepo, req, productionModule,
  setupBrowser, params, runProbe} from '../support.mjs';

await runProbe('1014', async () => {
  const RequestParams = await req();
  const StyleScope = (await mod('src/js/snapshot/style-scope.js')).default;
  const scope = new StyleScope();
  scope.defineFont('My\\26 Font');
  scope.addFontReference('My\\26 Font');
  const used = scope.toObject().usedFont;
  assert.equal(used['My&Font'], true);
});
