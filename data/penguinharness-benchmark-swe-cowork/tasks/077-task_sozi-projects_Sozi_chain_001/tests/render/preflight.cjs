'use strict';
const {app, BrowserWindow, ipcMain} = require('electron');
const fs = require('fs');
const path = require('path');
app.setPath('userData', process.env.SOZI_PREFLIGHT_DIR);
app.disableHardwareAcceleration();
ipcMain.once('sozi-preflight-result', (event, result) => {
  console.log(JSON.stringify(result));
  app.exit(result.ok ? 0 : 2);
});
app.on('ready', async () => {
  try {
    if (process.versions.electron !== '9.2.1') throw new Error('Verifier requires Electron 9.2.1');
    const window = new BrowserWindow({show: false, webPreferences: {nodeIntegration: true, contextIsolation: false, enableRemoteModule: true}});
    const html = path.join(process.env.SOZI_PREFLIGHT_DIR, 'host.html');
    fs.writeFileSync(html, '<!doctype html><body><h1>Verifier runtime</h1><script>require(' +
      JSON.stringify(path.join(__dirname, 'preflight-renderer.cjs')) + ')</script></body>');
    await window.loadURL('file://' + html);
    const value = await window.webContents.executeJavaScript('20 + 22');
    if (value !== 42) throw new Error('Chromium execution unavailable');
    window.webContents.send('sozi-preflight-check');
  }
  catch (error) { console.error(error); app.exit(2); }
});
setTimeout(() => app.exit(2), 20000);
