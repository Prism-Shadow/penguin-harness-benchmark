'use strict';
const fs=require('fs'), path=require('path');
const {createRequire}=require('module');
const project=createRequire('/app/code/package.json');
const {Cache}=project('@electron/get/dist/cjs/Cache');
const base='https://github.com/electron/electron/releases/download/v9.2.1/';
const roots=['/opt/sozi-runtime/electron-assets','/opt/sozi-runtime/downloads','/opt/verified-electron-9.2.1'];
for (const name of ['electron-v9.2.1-linux-x64.zip','SHASUMS256.txt']) {
 const source=roots.map(root=>path.join(root,name)).find(file=>fs.existsSync(file));
 if (!source) throw new Error('Missing verified Electron packaging asset: '+name);
 const destination=new Cache().getCachePath(base+name,name);
 fs.mkdirSync(path.dirname(destination),{recursive:true});fs.copyFileSync(source,destination);
 console.log('Seeded verified public Electron asset: '+name);
}
