import {assert, path, readFile, root, mod, fromRepo, req, productionModule,
  setupBrowser, params, runProbe} from '../support.mjs';

await runProbe('1009', async () => {
  const RequestParams = await req();
  const {ExtMsg} = await setupBrowser();
  const Capturer = (await mod('src/js/capturer/picture.js')).default;
  const p = params(RequestParams, {htmlCaptureImage: 'saveCurrent'});
  const node = {type: 1, name: 'PICTURE', attr: {}, childNodes: [
    {type: 1, name: 'SOURCE', attr: {srcset: 'a.jpg 1x', type: 'image/jpeg'}},
    {type: 1, name: 'IMG', attr: {src: 'a.jpg'}},
  ]};
  ExtMsg.mockGetUniqueFilename();
  const r = await Capturer.capture(node, p);
  assert.equal(r.tasks.length, 0);
  assert.equal(node.childNodes[0].change.ignore, true);
  assert.equal(node.childNodes[0].change.ignoreReason, 'capture method: saveCurrent');
  ExtMsg.clearMocks();
});
