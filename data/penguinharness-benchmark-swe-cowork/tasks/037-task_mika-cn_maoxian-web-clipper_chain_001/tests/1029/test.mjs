import {assert, path, readFile, root, mod, fromRepo, req, productionModule,
  setupBrowser, params, runProbe} from '../support.mjs';

await runProbe('1029', async () => {
  const RequestParams = await req();
  const {JSDOM} = fromRepo('jsdom');
  const {window} = new JSDOM('<div><span class="target"></span><span class="sibling"></span></div>');
  global.window = window; global.document = window.document; global.CustomEvent = window.CustomEvent;
  const Event = (await mod('src/js/lib/event.js')).default;
  const Plan = (await mod('src/js/assistant/plan.js')).default;
  Plan.apply({hideSibling: '.target'});
  Event.dispatchInternal('selecting');
  assert.equal(window.document.querySelector('.sibling').style.display, 'none');
});
