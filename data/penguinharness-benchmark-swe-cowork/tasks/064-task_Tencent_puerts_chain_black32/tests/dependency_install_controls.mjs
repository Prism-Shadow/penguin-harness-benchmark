import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { existsSync, mkdirSync, mkdtempSync, readFileSync, readdirSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { spawnSync } from 'node:child_process';
import { createRequire } from 'node:module';
import { test } from 'node:test';
import { installDependencies, installProject, registryLock } from '../environment/install-dependencies.mjs';

const root = mkdtempSync(join(tmpdir(), 'dependency-controls-'));
const require = createRequire(import.meta.url);
const originalOffline = process.env.npm_config_offline;
process.env.npm_config_offline = 'true';
process.env.npm_config_userconfig = join(root, 'empty-npmrc');
writeFileSync(process.env.npm_config_userconfig, '');

function command(executable, args) {
  const result = spawnSync(executable, args, { encoding: 'utf8' });
  assert.equal(result.status, 0, result.stdout + result.stderr);
}

function fixture(name, integrityOverride) {
  const project = join(root, name);
  const staging = join(root, name + '-staging');
  mkdirSync(project);
  mkdirSync(staging);
  const manifest = { name, version: '1.0.0', dependencies: { 'dependency-fixture': '1.0.0' } };
  const lock = { name, version: '1.0.0', lockfileVersion: 3, packages: {
    '': manifest,
    'node_modules/dependency-fixture': {
      version: '1.0.0', resolved: 'https://mirrors.tencent.com/npm/dependency-fixture/-/dependency-fixture-1.0.0.tgz',
      integrity: integrityOverride ?? integrity,
    },
  } };
  writeFileSync(join(project, 'package.json'), JSON.stringify(manifest));
  writeFileSync(join(project, 'package-lock.json'), JSON.stringify(lock));
  command('npm', ['cache', 'add', archive, '--cache=' + join(staging, 'cache'), '--ignore-scripts', '--offline']);
  return { project, staging };
}

const packageDirectory = join(root, 'package');
mkdirSync(packageDirectory);
writeFileSync(join(packageDirectory, 'package.json'), JSON.stringify({
  name: 'dependency-fixture', version: '1.0.0', main: 'index.js',
  scripts: { install: 'node -e "process.exit(91)"' },
}));
writeFileSync(join(packageDirectory, 'index.js'), 'module.exports = input => input * 7;\n');
const archive = join(root, 'fixture.tgz');
command('tar', ['-czf', archive, '-C', root, 'package']);
const integrity = 'sha512-' + createHash('sha512').update(readFileSync(archive)).digest('base64');

try {
  await test('all 162 locked URLs change transport only, including scoped packages', () => {
    let count = 0;
    for (const project of ['agent_proj', 'mcp_proj']) {
      const lock = JSON.parse(readFileSync(join(process.env.REPO_DIR || '/app/code', 'unity', project, 'package-lock.json')));
      const snapshot = structuredClone(lock);
      const normalized = registryLock(lock);
      for (const [key, entry] of Object.entries(lock.packages)) {
        if (!entry.resolved) continue;
        const updated = normalized.packages[key];
        assert.equal(updated.resolved, entry.resolved.replace('https://mirrors.tencent.com/npm/', 'https://registry.npmjs.org/'));
        assert.deepEqual({ ...updated, resolved: entry.resolved }, entry);
        count++;
      }
      assert.deepEqual(lock, snapshot);
      assert.deepEqual({ ...normalized, packages: lock.packages }, lock);
    }
    assert.equal(count, 162);
    const untouched = { lockfileVersion: 3, packages: { other: { resolved: 'https://other.invalid/pkg.tgz', integrity } } };
    assert.deepEqual(registryLock(untouched), untouched);
  });
  await test('missing integrity fails closed', () => {
    assert.throws(() => registryLock({ lockfileVersion: 3, packages: {
      broken: { resolved: 'https://mirrors.tencent.com/npm/broken.tgz' },
    } }), /missing locked integrity/);
  });
  await test('real npm ci installs executable dependency, ignores scripts, preserves baseline manifests', () => {
    const { project, staging } = fixture('positive');
    const before = ['package.json', 'package-lock.json'].map(name => readFileSync(join(project, name)));
    installProject(project, staging);
    assert.equal(require(join(project, 'node_modules/dependency-fixture'))(6), 42);
    for (const [index, name] of ['package.json', 'package-lock.json'].entries()) {
      assert.deepEqual(readFileSync(join(project, name)), before[index]);
    }
    assert.deepEqual(readdirSync(staging), ['cache']);
    assert.throws(() => installProject(project, staging), /clean dependency destination/);
  });
  await test('wrong integrity cannot install cached bytes or leave partial output', () => {
    const { project, staging } = fixture('bad-integrity', 'sha512-' + Buffer.alloc(64).toString('base64'));
    assert.throws(() => installProject(project, staging), /npm ci failed/);
    assert.equal(existsSync(join(project, 'node_modules')), false);
    assert.deepEqual(readdirSync(staging), ['cache']);
  });
  await test('manifest/lock mismatch remains a hard npm ci failure', () => {
    const { project, staging } = fixture('bad-lock');
    const manifestPath = join(project, 'package.json');
    const manifest = JSON.parse(readFileSync(manifestPath));
    manifest.dependencies['dependency-fixture'] = '2.0.0';
    writeFileSync(manifestPath, JSON.stringify(manifest));
    assert.throws(() => installProject(project, staging), /npm ci failed/);
    assert.equal(existsSync(join(project, 'node_modules')), false);
    assert.deepEqual(readdirSync(staging), ['cache']);
  });
  await test('top-level failure cleans only its own temporary cache', () => {
    const before = readdirSync(tmpdir()).filter(name => name.startsWith('puerts-dependencies-')).sort();
    assert.throws(() => installDependencies(join(root, 'missing-workspace')), /ENOENT/);
    const after = readdirSync(tmpdir()).filter(name => name.startsWith('puerts-dependencies-')).sort();
    assert.deepEqual(after, before);
  });
} finally {
  if (originalOffline === undefined) delete process.env.npm_config_offline;
  else process.env.npm_config_offline = originalOffline;
  rmSync(root, { recursive: true, force: true });
}
