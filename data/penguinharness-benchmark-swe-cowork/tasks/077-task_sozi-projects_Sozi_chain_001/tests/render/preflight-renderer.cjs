'use strict';

const path = require('path');
const {createRequire} = require('module');
const {ipcRenderer} = require('electron');
const fromBuild = createRequire(path.join(process.env.SOZI_PREFLIGHT_DIR, 'package.json'));

ipcRenderer.once('sozi-preflight-check', () => {
  try {
    const modules = {};
    for (const name of ['pdf-lib', 'officegen', 'tmp', 'nunjucks', 'inferno', 'inferno-hyperscript', 'jed']) {
      fromBuild(name);
      modules[name] = fromBuild.resolve(name);
    }
    ipcRenderer.send('sozi-preflight-result', {ok: true, modules});
  }
  catch (error) {
    ipcRenderer.send('sozi-preflight-result', {ok: false, error: error.stack});
  }
});
