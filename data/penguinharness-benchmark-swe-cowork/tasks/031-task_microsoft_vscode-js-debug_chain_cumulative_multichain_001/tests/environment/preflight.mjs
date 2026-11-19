import assert from 'node:assert/strict';
import './preflight.cjs';
import { project } from './loader_probe.mts';

assert.deepEqual([project(-3), project(7)], [-5, 15]);
console.log('shared contract loader and TypeScript execution preflight passed');
