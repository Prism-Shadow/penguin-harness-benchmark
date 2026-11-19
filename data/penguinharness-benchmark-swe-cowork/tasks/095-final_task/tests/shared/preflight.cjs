'use strict';
const Module = require('module');
const path = require('path');
require('@babel/core');
require('vue-template-compiler');
require('jsdom');
const application = Module.createRequire(path.join(process.env.WORKSPACE_ROOT, 'package.json'));
for (const dependency of ['vue', 'chalk', 'webpack', 'eslint', 'ioredis']) application(dependency);
process.stdout.write('Verifier and application runtimes loaded\n', () => process.exit(0));
