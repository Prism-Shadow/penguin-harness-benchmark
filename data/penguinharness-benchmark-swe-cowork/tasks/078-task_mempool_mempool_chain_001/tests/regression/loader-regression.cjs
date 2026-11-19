const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const Module = require('node:module');
const { loadProduction } = require('../support/ts-loader.cjs');

test('loader executes split helpers, rejects missing boundaries and restores cache', () => {
  const root = fs.mkdtempSync(path.join(process.env.REPAIR_TMP_DIR, 'loader-'));
  const originalRepo = process.env.REPO_DIR;
  process.env.REPO_DIR = root;
  try {
    const entry = path.join(root, 'entry.ts');
    const helper = path.join(root, 'helper.ts');
    fs.writeFileSync(entry, "import { scale } from './helper'; export const calculate = (value: number) => scale(value) + 1;");
    fs.writeFileSync(helper, 'export const scale = (value: number) => value * 3;');
    const first = loadProduction(entry);
    assert.equal(first.calculate(4), 13);
    assert.equal(first.calculate(-2), -5);
    fs.writeFileSync(helper, 'export const scale = (value: number) => value * 5;');
    assert.equal(loadProduction(entry).calculate(4), 21);
    fs.writeFileSync(helper, 'export const = ;');
    assert.throws(() => loadProduction(entry), /TEST_SOLVER_COMPILE/);
    fs.writeFileSync(helper, "import missing from 'undeclared-runtime'; export const scale = missing;");
    assert.throws(() => loadProduction(entry), /TEST_SETUP_ERROR/);
    fs.unlinkSync(helper);
    assert.throws(() => loadProduction(entry), /TEST_LOAD_ERROR/);
  } finally {
    if (originalRepo === undefined) delete process.env.REPO_DIR;
    else process.env.REPO_DIR = originalRepo;
    fs.rmSync(root, { recursive: true });
  }
});

test('loader keeps deferred production imports real and restores hooks after rejection', async () => {
  const root = fs.mkdtempSync(path.join(process.env.REPAIR_TMP_DIR, 'deferred-loader-'));
  const originalRepo = process.env.REPO_DIR;
  const originalLoad = Module._load;
  const originalTs = require.extensions['.ts'];
  process.env.REPO_DIR = root;
  try {
    const entry = path.join(root, 'entry.ts');
    const helper = path.join(root, 'helper.ts');
    fs.writeFileSync(entry, "export const calculate = async () => (await import('./helper')).value;");
    fs.writeFileSync(helper, 'export const value = 37;');
    assert.equal(await loadProduction(entry, {}, async production => {
      await Promise.resolve();
      return production.calculate();
    }), 37);
    assert.equal(Module._load, originalLoad);
    assert.equal(require.extensions['.ts'], originalTs);
    assert.equal(require.cache[helper], undefined);
    fs.writeFileSync(helper, 'export const = ;');
    await assert.rejects(loadProduction(entry, {}, production => production.calculate()), /TEST_SOLVER_COMPILE/);
    fs.unlinkSync(helper);
    await assert.rejects(loadProduction(entry, {}, production => production.calculate()), /TEST_LOAD_ERROR/);
    fs.writeFileSync(helper, "import missing from 'undeclared-runtime'; export const value = missing;");
    await assert.rejects(loadProduction(entry, {}, production => production.calculate()), /TEST_SETUP_ERROR/);
    assert.equal(Module._load, originalLoad);
    assert.equal(require.extensions['.ts'], originalTs);
    assert.equal(require.cache[entry], undefined);
  } finally {
    if (originalRepo === undefined) delete process.env.REPO_DIR;
    else process.env.REPO_DIR = originalRepo;
    fs.rmSync(root, { recursive: true });
  }
});
