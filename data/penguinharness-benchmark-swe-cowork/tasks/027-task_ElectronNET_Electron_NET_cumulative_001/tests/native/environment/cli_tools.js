const fs = require('node:fs');
const path = require('node:path');

const [command, ...args] = process.argv.slice(2);
fs.appendFileSync(process.env.PROBE_PROCESS_LOG, JSON.stringify({ command, args, cwd: process.cwd() }) + '\n');
if (command === 'dotnet' && args[0] === 'publish') {
  if (process.env.PROBE_PUBLISH_EXIT) process.exit(Number(process.env.PROBE_PUBLISH_EXIT));
  const output = args[args.indexOf('--output') + 1];
  if (!output) throw new Error('publish must identify its output directory');
  fs.mkdirSync(output, { recursive: true });
  fs.writeFileSync(path.join(output, 'electron.manifest.json'), JSON.stringify({ name: 'Fixture App', build: { buildVersion: '3.8.1' } }));
} else if (command === 'npm' && args[0] === 'install') {
  const bin = path.join(process.cwd(), 'node_modules', '.bin');
  fs.mkdirSync(bin, { recursive: true });
  const quote = value => `'${value.replace(/'/g, "'\\''")}'`;
  fs.writeFileSync(path.join(bin, 'electron'), `#!/bin/sh\nexec ${quote(process.env.PROBE_REAL_NODE)} ${quote(__filename)} electron "$@"\n`, { mode: 0o755 });
} else if (!['node', 'npx', 'electron'].includes(command)) {
  throw new Error(`Unexpected external command ${command}`);
}
