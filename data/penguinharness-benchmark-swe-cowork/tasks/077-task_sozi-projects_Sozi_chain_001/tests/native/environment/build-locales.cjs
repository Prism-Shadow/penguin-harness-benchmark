'use strict';

const fs = require('node:fs');
const path = require('node:path');
const {execFileSync} = require('node:child_process');

const root = path.resolve(process.argv[2] || '/workspace');
const localeDir = path.join(root, 'locales');
const output = path.join(root, 'js', 'locales.js');
const po2json = require.resolve('po2json/bin/po2json');
const localeData = {};

for (const file of fs.readdirSync(localeDir).filter(name => name.endsWith('.po')).sort()) {
  const locale = file.slice(0, -3);
  const tempDir = fs.mkdtempSync(path.join('/tmp', 'sozi-locale-'));
  const tempOutput = path.join(tempDir, `${locale}.json`);
  execFileSync(process.execPath, [po2json, path.join(localeDir, file), tempOutput, '-f', 'jed1.x'], {encoding: 'utf8'});
  localeData[locale] = JSON.parse(fs.readFileSync(tempOutput, 'utf8'));
  fs.rmSync(tempDir, {recursive: true, force: true});
}

fs.writeFileSync(output, `module.exports = ${JSON.stringify(localeData)};\n`, 'utf8');
