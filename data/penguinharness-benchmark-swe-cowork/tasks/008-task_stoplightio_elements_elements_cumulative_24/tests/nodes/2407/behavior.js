const { ROOT, req, assert, equal, reportFailure } = require('./behavior-setup');

(async () => {

const security = req('packages/elements-core/src/utils/oas/security');
const schemes = [
  { id: 'one', key: 'one', type: 'apiKey', name: 'x-api-key', in: 'header' },
  { id: 'two', key: 'two', type: 'apiKey', name: 'x-api-key-2', in: 'header' },
];
assert(typeof security.getReadableSecurityNames === 'function', 'AND security names are available');
equal(security.getReadableSecurityNames(schemes), 'API Key (one) & API Key (two)', 'AND security names preserve distinct keys');
assert(security.shouldAddKey([schemes[0]], [[schemes[0]], [schemes[1]]]), 'single-scheme groups add a key when the same type repeats');

})().then(() => process.exit(0)).catch(reportFailure);
