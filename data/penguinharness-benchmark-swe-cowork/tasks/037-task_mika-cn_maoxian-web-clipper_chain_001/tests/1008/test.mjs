import {assert, path, readFile, root, mod, fromRepo, req, productionModule,
  setupBrowser, params, runProbe} from '../support.mjs';

await runProbe('1008', async () => {
  const RequestParams = await req();
  const {ExtMsg} = await setupBrowser();
  const Capturer = (await mod('src/js/capturer/img.js')).default;
  const p = params(RequestParams, {htmlCaptureImage: 'saveCurrent'});
  const node = {type: 1, name: 'IMG', attr: {src: 'fallback.jpg', srcset: 'fallback.jpg 1x'}, currentSrc: 'current.svg'};
  ExtMsg.mockGetUniqueFilename();
  const r = await Capturer.capture(node, {...p, saveFormat: 'html'});
  const c = r.change.toChangeObjectAccessor();
  assert.equal(r.tasks.length, 1);
  assert.match(c.getAttr('src'), /\.svg$/);
  assert.equal(c.deletedAttr('srcset'), true);
  assert.equal(c.getAttr('data-mx-original-src'),'fallback.jpg');
  assert.equal(c.getAttr('data-mx-original-srcset'),'fallback.jpg 1x');
  ExtMsg.clearMocks();
});
