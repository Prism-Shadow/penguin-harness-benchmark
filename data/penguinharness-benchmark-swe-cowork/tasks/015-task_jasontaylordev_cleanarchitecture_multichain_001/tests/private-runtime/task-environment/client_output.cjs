const fs = require('node:fs');
const path = require('node:path');
const { createRequire } = require('node:module');
const { pathToFileURL } = require('node:url');

async function main() {
  let directory;
  if (process.argv[2] === 'ClientApp-React') {
    const localRequire = createRequire(path.join(process.cwd(), 'package.json'));
    const vite = await import(pathToFileURL(localRequire.resolve('vite')).href);
    const config = await vite.resolveConfig({}, 'build', 'production');
    directory = path.resolve(config.root, config.build.outDir);
  } else {
    const config = JSON.parse(fs.readFileSync('angular.json', 'utf8'));
    const projects = Object.values(config.projects).filter(project => project.projectType === 'application');
    if (projects.length !== 1) throw new Error('Expected one Angular application build target');
    const target = (projects[0].architect || projects[0].targets).build;
    const options = { ...target.options, ...target.configurations?.[target.defaultConfiguration] };
    const output = options.outputPath;
    const base = typeof output === 'string' ? output : output.base;
    const browser = typeof output === 'object' ? output.browser ?? 'browser' : 'browser';
    directory = path.resolve(base, /:application$/.test(target.builder) ? browser : '');
  }
  fs.writeFileSync(process.argv[3], JSON.stringify({ directory }));
}

main().catch(error => {
  console.error(error);
  process.exitCode = 3;
});
