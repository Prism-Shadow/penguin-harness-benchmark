'use strict';

const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const {spawnSync} = require('node:child_process');
const {test} = require('node:test');
const {linkModules} = require('./dependencies.cjs');

function fixture(context) {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'sozi-dependencies-'));
  context.after(() => fs.rmSync(root, {recursive: true, force: true}));
  const source = path.join(root, 'submission');
  const runtime = path.join(root, 'runtime', 'node_modules');
  const built = path.join(root, 'artifacts', 'build');
  for (const directory of [path.join(source, 'node_modules'), runtime, built]) fs.mkdirSync(directory, {recursive: true});
  return {source, runtime, built};
}

function packageFile(directory, name, code) {
  const target = path.join(directory, name);
  fs.mkdirSync(target, {recursive: true});
  fs.writeFileSync(path.join(target, 'index.js'), code);
}

function evaluate(built, code) {
  const consumer = path.join(built, 'consumer.cjs');
  fs.writeFileSync(consumer, code);
  return spawnSync(process.execPath, [consumer], {encoding: 'utf8', env: {...process.env, NODE_PATH: '', NODE_OPTIONS: ''}});
}

test('artifact consumer loads runtime fallback and transitive dependencies without NODE_PATH', context => {
  const {source, runtime, built} = fixture(context);
  packageFile(runtime, 'export-library', "module.exports = require('helper') + 1;");
  packageFile(runtime, 'helper', 'module.exports = 41;');
  linkModules(source, built, runtime);
  const result = evaluate(built, "console.log(require('export-library'));");
  assert.equal(result.status, 0, result.stderr);
  assert.equal(result.stdout.trim(), '42');
  assert.deepEqual(fs.readdirSync(path.join(source, 'node_modules')), []);
});

test('submitted packages take precedence and scopes merge without replacing versions', context => {
  const {source, runtime, built} = fixture(context);
  const modules = path.join(source, 'node_modules');
  packageFile(modules, 'shared', "module.exports = 'submission';");
  packageFile(runtime, 'shared', "module.exports = 'runtime';");
  packageFile(modules, '@scope/shared', "module.exports = 'scoped submission';");
  packageFile(runtime, '@scope/shared', "module.exports = 'scoped runtime';");
  packageFile(runtime, '@scope/fallback', "module.exports = 'scoped fallback';");
  linkModules(source, built, runtime);
  const result = evaluate(built, "console.log(JSON.stringify(['shared', '@scope/shared', '@scope/fallback'].map(name => require(name))));");
  assert.equal(result.status, 0, result.stderr);
  assert.deepEqual(JSON.parse(result.stdout), ['submission', 'scoped submission', 'scoped fallback']);
  assert.deepEqual(fs.readdirSync(path.join(modules, '@scope')), ['shared']);
});

test('old repository-only link reproduces missing provisioned dependency', context => {
  const {source, runtime, built} = fixture(context);
  packageFile(runtime, 'export-library', 'module.exports = 42;');
  fs.symlinkSync(path.join(source, 'node_modules'), path.join(built, 'node_modules'), 'dir');
  const result = evaluate(built, "require('export-library');");
  assert.notEqual(result.status, 0);
  assert.match(result.stderr, /Cannot find module 'export-library'/);
});

test('missing and broken packages remain errors rather than stubbed successes', context => {
  const {source, runtime, built} = fixture(context);
  packageFile(runtime, 'broken', "throw new Error('broken public dependency');");
  linkModules(source, built, runtime);
  for (const [name, message] of [['absent', /Cannot find module 'absent'/], ['broken', /broken public dependency/]]) {
    const result = evaluate(built, `require(${JSON.stringify(name)});`);
    assert.notEqual(result.status, 0);
    assert.match(result.stderr, message);
  }
});

test('missing provisioned runtime fails closed', context => {
  const {source, runtime, built} = fixture(context);
  fs.rmdirSync(runtime);
  assert.throws(() => linkModules(source, built, runtime), {code: 'ENOENT'});
});
