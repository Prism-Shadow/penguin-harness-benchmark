import {assert, path, readFile, root, mod, fromRepo, req, productionModule,
  setupBrowser, params, runProbe} from '../support.mjs';

await runProbe('1010', async () => {
  const RequestParams = await req();
  const {ExtMsg} = await setupBrowser();
  const Capturer = (await mod('src/js/capturer/audio.js')).default;
  const p = params(RequestParams, {htmlCaptureAudio: 'saveCurrent'});
  const node = {type: 1, name: 'AUDIO', attr: {src: 'fallback.mp3'}, currentSrc: 'current.ogg', childNodes: [
    {type: 1, name: 'SOURCE', attr: {src: 'fallback.mp3', type: 'audio/mpeg'}},
    {type: 1, name: 'TRACK', attr: {src: 'captions.vtt'}},
  ]};
  ExtMsg.mockGetUniqueFilename();
  const r = await Capturer.capture(node, p);
  assert.equal(r.tasks.length, 2);
  assert.match(r.tasks[0].url, /current\.ogg$/);
  assert.equal(node.childNodes[0].change.ignore, true);
  ExtMsg.clearMocks();
});
