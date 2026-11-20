const { createRequire } = require('node:module');
const path = require('node:path');
const root = process.env.REPO_ROOT;
const requireFromRepo = createRequire(path.join(root, 'package.json'));
// Build the real worker at Hasher's source-loaded runtime path.
requireFromRepo('esbuild').buildSync({
  entryPoints: [path.join(root, 'src/common/hash/hash.ts')],
  outfile: path.join(root, 'src/common/hash/hash.js'),
  bundle: true, packages: 'external', platform: 'node', format: 'cjs', target: 'node18',
});
console.log('production hash worker compiled');
