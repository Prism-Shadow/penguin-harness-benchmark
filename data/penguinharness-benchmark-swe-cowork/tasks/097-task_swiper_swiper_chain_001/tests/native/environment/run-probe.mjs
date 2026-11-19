import { spawnSync } from 'node:child_process';

export function runProbe(name) {
  const probe = new URL('./swiper-probe.mjs', import.meta.url).pathname;
  const result = spawnSync(process.execPath, [probe, name], { encoding: 'utf8', env: process.env });
  process.stdout.write(result.stdout || '');
  process.stderr.write(result.stderr || '');
  if (result.status === 0) {
    const completions = (result.stdout || '').split(/\r?\n/).filter((line) => line === `probe:${name}:pass`);
    if (completions.length !== 1) {
      process.stderr.write('PROBE_INCOMPLETE: production process exited before assertions completed\n');
      process.exit(1);
    }
  }
  if (result.error) process.stderr.write(`PROBE_INCOMPLETE: ${result.error.message}\n`);
  process.exit(result.status === null ? 1 : result.status);
}
