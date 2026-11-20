'use strict';

const fs = require('fs');
const path = require('path');
const {createRequire} = require('module');
const {linkModules} = require('./dependencies.cjs');
const source = path.resolve(process.argv[2]);
const destination = path.resolve(process.argv[3]);
const fromSource = createRequire(path.join(source, 'package.json'));
const babel = require('@babel/core');
const browserify = fromSource('browserify');
const nunjucks = require('nunjucks');

function compile(directory) {
  for (const entry of fs.readdirSync(path.join(source, directory), {withFileTypes: true})) {
    const relative = path.join(directory, entry.name);
    if (entry.isDirectory()) compile(relative);
    else if (entry.name.endsWith('.js')) {
      const target = path.join(destination, relative);
      fs.mkdirSync(path.dirname(target), {recursive: true});
      const result = babel.transformFileSync(path.join(source, relative), {
        babelrc: false, configFile: false,
        presets: [[require.resolve('@babel/preset-env'), {targets: {electron: '9.2'}}]],
      });
      fs.writeFileSync(target, result.code);
    }
  }
}

async function main() {
  compile('js');
  const locales = {};
  const po2json = require('po2json');
  for (const file of fs.readdirSync(path.join(source, 'locales')).filter(name => name.endsWith('.po'))) {
    locales[file.slice(0, -3)] = po2json.parseFileSync(path.join(source, 'locales', file), {format: 'jed1.x'});
  }
  fs.writeFileSync(path.join(destination, 'js/locales.js'), `module.exports = ${JSON.stringify(locales)};`);
  linkModules(source, destination);
  const bundle = await new Promise((resolve, reject) => {
    browserify(path.join(destination, 'js/player.js')).bundle((error, data) => error ? reject(error) : resolve(data));
  });
  fs.mkdirSync(path.join(destination, 'templates'), {recursive: true});
  const template = nunjucks.renderString(fs.readFileSync(path.join(source, 'templates/player.html'), 'utf8'), {js: bundle.toString()});
  fs.writeFileSync(path.join(destination, 'templates/player.html'), template);
  console.log('Built production Controller/exporter/preload/Player from submitted source.');
}

main().catch(error => { console.error(error.stack); process.exitCode = 1; });
