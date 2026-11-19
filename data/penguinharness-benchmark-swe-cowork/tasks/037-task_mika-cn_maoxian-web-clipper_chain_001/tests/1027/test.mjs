import {assert, path, readFile, root, mod, fromRepo, req, productionModule,
  setupBrowser, params, runProbe} from '../support.mjs';

await runProbe('1027', async () => {
  const RequestParams = await req();
  const {ExtMsg} = await setupBrowser();
  const Capturer = (await mod('src/js/capturer/video.js')).default;
  const p = params(RequestParams, {htmlCaptureVideo: 'saveAll'});
  const node = {type: 1, name: 'VIDEO', attr: {src: 'v.mp4', controlslist: 'nodownload', disablepictureinpicture: '', autopictureinpicture: '', autoplay: '', loop: '', muted: '', crossorigin: ''}, childNodes: []};
  ExtMsg.mockGetUniqueFilename();
  const r = await Capturer.capture(node, p);
  const c = r.change.toChangeObjectAccessor();
  assert.equal(c.deletedAttr('controlslist'), true);
  assert.equal(c.deletedAttr('disablepictureinpicture'), true);
  assert.equal(c.deletedAttr('autopictureinpicture'), true);
  ExtMsg.clearMocks();
});
