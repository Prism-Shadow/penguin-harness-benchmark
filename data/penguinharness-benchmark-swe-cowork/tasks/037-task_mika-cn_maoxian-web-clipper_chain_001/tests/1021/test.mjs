import {assert, path, readFile, root, mod, fromRepo, req, productionModule,
  setupBrowser, params, runProbe} from '../support.mjs';

await runProbe('1021', async () => {
  const RequestParams = await req();
  const WhiteSpace = (await productionModule('src/js/lib/white-space.js')).default;
  const Capturer = (await mod('src/js/capturer/stylesheet.js')).default;
  const {CSSRULE_TYPE} = await mod('src/js/lib/constants.js');
  // The original checkpoint called this policy saveWoff.  Later filter
  // migration renamed it to filterList while preserving the WOFF contract.
  const p = params(RequestParams, {htmlCaptureWebFont: 'saveWoff'});
  p.baseUrl = p.docBaseUrl;
  p.ownerType = 'styleNode';
  p.whiteSpace = WhiteSpace.create({step: 2, compress: false});
  const sheet = {url: 'https://a.org/style.css', disabled: false, title: '', rules: [
    {type: CSSRULE_TYPE.FONT_FACE, styleObj: {src: 'url(a.woff)'}},
  ]};
  const {ExtMsg} = await setupBrowser();
  const capture = async (option) => {
    ExtMsg.clearMocks();
    ExtMsg.mockGetUniqueFilename();
    return Capturer.captureStyleSheet(sheet, {
      ...p,
      config: {
        ...p.config,
        htmlCaptureWebFont: option,
        htmlWebFontFilterList: 'woff2|woff',
      },
    });
  };
  let r;
  try {
    r = await capture('saveWoff');
  } catch (_error) {
    r = null;
  }
  if (!r || r.tasks.length === 0) {
    r = await capture('filterList');
  }
  assert.equal(r.tasks.length, 1);
  assert.match(r.tasks[0].url, /a\.woff$/);
  ExtMsg.clearMocks();
});
