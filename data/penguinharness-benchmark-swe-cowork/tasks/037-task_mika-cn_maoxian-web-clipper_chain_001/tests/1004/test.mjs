import {assert, path, readFile, root, mod, fromRepo, req, productionModule,
  setupBrowser, params, runProbe} from '../support.mjs';

await runProbe('1004', async () => {
  const RequestParams = await req();
  const {ExtMsg} = await setupBrowser();
  const Capturer = (await productionModule('src/js/capturer/video.js')).default;
  const p = params(RequestParams, {htmlCaptureVideo: 'saveAll'});
  const node = {type: 1, name: 'VIDEO', attr: {src: 'v.mp4'}, currentSrc: 'v.mp4', childNodes: []};
  ExtMsg.mockGetUniqueFilename();
  const r = await Capturer.capture(node, p);
  assert.equal(r.tasks.length, 1);
  assert.equal(r.tasks[0].taskType, 'videoFileTask');
  assert.equal(r.change.toChangeObjectAccessor().deletedAttr('crossorigin'), true);
  ExtMsg.clearMocks();
});
