import {assert, path, readFile, root, mod, fromRepo, req, productionModule,
  setupBrowser, params, runProbe} from '../support.mjs';

await runProbe('1019', async () => {
  const RequestParams = await req();
  const {ExtMsg} = await setupBrowser();
  const Capturer = (await mod('src/js/capturer/link.js')).default;
  const p = params(RequestParams, {htmlCaptureIcon: 'saveFavicon', saveIcon: true});
  const node = {type: 1, name: 'LINK', attr: {rel: 'apple-touch-icon-precomposed', href: '/touch.png'}, relList: ['apple-touch-icon-precomposed']};
  ExtMsg.mockGetUniqueFilename();
  ExtMsg.mockMsgResult('get.mimeType', 'image/png');
  const r = await Capturer.capture(node, p);
  assert.equal(r.tasks.length, 0);
  assert.equal(r.change.toChangeObjectAccessor().getProperty('ignore'), true);
  ExtMsg.clearMocks();
  const saveAll = params(RequestParams, {htmlCaptureIcon: 'saveAll'});
  ExtMsg.mockGetUniqueFilename();
  ExtMsg.mockMsgResult('get.mimeType', 'image/png');
  const saved = await Capturer.capture(node, saveAll);
  assert.equal(saved.tasks.length, 1);
  ExtMsg.clearMocks();
});
