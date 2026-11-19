'use strict';

const fs = require('fs');
const path = require('path');

function linkModules(source, destination, runtimeModules = '/opt/sozi-runtime/node_modules') {
  const target = path.join(destination, 'node_modules');
  fs.mkdirSync(target, {recursive: true});
  for (const directory of [path.join(source, 'node_modules'), runtimeModules]) {
    for (const entry of fs.readdirSync(directory, {withFileTypes: true})) {
      if (entry.name.startsWith('.')) continue;
      const origin = path.join(directory, entry.name);
      const link = path.join(target, entry.name);
      if (entry.name.startsWith('@')) {
        fs.mkdirSync(link, {recursive: true});
        for (const name of fs.readdirSync(origin)) {
          const scoped = path.join(link, name);
          if (!fs.existsSync(scoped)) fs.symlinkSync(path.resolve(origin, name), scoped, 'dir');
        }
      }
      else if (!fs.existsSync(link)) fs.symlinkSync(path.resolve(origin), link, 'dir');
    }
  }
}

module.exports = {linkModules};
if (require.main === module) linkModules(path.resolve(process.argv[2]), path.resolve(process.argv[3]));
