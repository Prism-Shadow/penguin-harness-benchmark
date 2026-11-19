import {assert, path, readFile, root, mod, fromRepo, req, productionModule,
  setupBrowser, params, runProbe} from '../support.mjs';

await runProbe('1020', async () => {
  const RequestParams = await req();
  const StyleSheet = (await mod('src/js/snapshot/stylesheet.js')).default;
  const sheet = {type: 'text/css', href: 'https://a.org/a.css', disabled: false, title: '', media: {mediaText: 'all', length: 0}, cssRules: []};
  const out = await StyleSheet.take(sheet, {requestParams: RequestParams.createExample(), win: {document: {}}, platform: {isChrome: true}, alternative: true});
  assert.equal(out.disabled, true);
});
