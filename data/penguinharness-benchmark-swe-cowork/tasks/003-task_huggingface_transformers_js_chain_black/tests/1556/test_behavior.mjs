import assert from 'node:assert/strict';
import { load } from '../support/load.mjs';

        const { apis } = await load('packages/transformers/src/env.js');
assert.equal(Object.prototype.hasOwnProperty.call(apis, 'IS_WEB_ENV'), true);
assert.equal(apis.IS_WEB_ENV, false);

import { runScript } from '../support/run-script.mjs';
runScript(new URL('../support/web-recovery.mjs', import.meta.url));
