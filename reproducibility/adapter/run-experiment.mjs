import { DatabaseSync } from 'node:sqlite';
import { spawn } from 'node:child_process';
import { homedir } from 'node:os';
import { join } from 'node:path';

const methods = new Set(['openskill', 'skilladam', 'trace', 'skillopt']);
const domains = new Set(['service-ticket-resolution', 'financial-control', 'portfolio-management',
  'coverage-review', 'court-clerk-operations', 'engineering-portfolio-analytics']);
const [method, domain, phase, skill] = process.argv.slice(2);
if (!methods.has(method) || !domains.has(domain) || !['train', 'retry-train', 'resume-train', 'baseline', 'test', 'retry-test', 'supplement-test', 'supplement-baseline', 'supplement-baseline-rest', 'supplement-baseline-final'].includes(phase)
    || (['test', 'retry-test', 'supplement-test'].includes(phase) && !skill?.startsWith('/mnt/c/'))) {
  throw new Error('Expected a supported method, domain, phase, and frozen Skill path for testing.');
}
const db = new DatabaseSync(join(homedir(), '.cc-switch', 'cc-switch.db'), { readOnly: true });
let key;
try {
  for (const row of db.prepare('SELECT settings_config FROM providers ORDER BY is_current DESC').all()) {
    const value = JSON.parse(row.settings_config);
    if (!JSON.stringify(value).includes('api.deepseek.com')) continue;
    const env = value.env ?? {};
    key = env.DEEPSEEK_API_KEY ?? env.ANTHROPIC_AUTH_TOKEN ?? env.ANTHROPIC_API_KEY ?? value.auth?.OPENAI_API_KEY;
    if (typeof key === 'string' && key.startsWith('sk-')) break;
    key = undefined;
  }
} finally {
  db.close();
}
if (!key) throw new Error('DeepSeek credential not found in CC Switch.');

const root = '/mnt/c/Users/13689/OneDrive/桌面/penguin_HARNESS/codex-rsi-adapter';
const plan = `${root}/experiments/${method}/${domain}`;
const jobs = `${root}/jobs/${phase === 'baseline' ? 'baseline' : method}-${domain}-${phase}`;
const env = { ...process.env, OPENAI_API_KEY: key, OPENAI_BASE_URL: 'https://api.deepseek.com',
  WSLENV: 'OPENAI_API_KEY/u:OPENAI_BASE_URL/u:DOCKER_HOST/u' };
const completedSupplement = { 'court-clerk-operations': '001', 'coverage-review': '003' };
const resumable = {
  'skillopt-financial-control': 'skillopt-financial-control-train/2026-11-15__22-19-00/train_tasks__H6McQxJ',
  'skillopt-portfolio-management': 'skillopt-portfolio-management-train/2026-11-15__22-19-01/train_tasks__vpSATsQ',
  'skillopt-engineering-portfolio-analytics': 'interrupted-engineering-skillopt-recovery',
};
if (phase === 'resume-train' && !resumable[`${method}-${domain}`]) {
  throw new Error('No saved session is configured for this method and domain.');
}
if (['supplement-baseline-rest', 'supplement-baseline-final'].includes(phase) && !completedSupplement[domain]) {
  throw new Error('No prior completed supplement is configured for this domain.');
}
if (phase === 'supplement-baseline-final' && domain !== 'court-clerk-operations') {
  throw new Error('Final supplement is only configured for the court baseline.');
}
const work = phase === 'resume-train'
  ? [`${root}/resume-training.py`, '--plan', plan, '--trial', `${root}/jobs/${resumable[`${method}-${domain}`]}`,
     '--jobs', jobs]
  : phase === 'supplement-test'
  ? [`${root}/supplement.py`, '--plan', plan, '--phase', 'test', '--skill', skill,
     '--source', `${root}/jobs/${method}-${domain}-test`,
     '--jobs', `${root}/jobs/${method}-${domain}-test-supplement`, '--execute']
  : phase.startsWith('supplement-baseline')
  ? [`${root}/supplement.py`, '--plan', plan, '--phase', 'baseline',
     '--source', `${root}/jobs/baseline-${domain}-baseline`,
     ...(['supplement-baseline-rest', 'supplement-baseline-final'].includes(phase)
       ? ['--source', `${root}/jobs/${domain}-baseline-supplement/${domain}-test-${completedSupplement[domain]}`]
       : []),
     ...(phase === 'supplement-baseline-final'
       ? ['--source', `${root}/jobs/${domain}-baseline-supplement-2/${domain}-test-002`]
       : []),
     '--jobs', `${root}/jobs/${domain}-baseline-supplement${phase === 'supplement-baseline-rest' ? '-2' : phase === 'supplement-baseline-final' ? '-3' : ''}`, '--execute']
  : [`${root}/adapter.py`, 'run', '--plan', plan, '--phase', phase === 'retry-train' ? 'train' : phase === 'retry-test' ? 'test' : phase, '--jobs', jobs,
     ...(['test', 'retry-test'].includes(phase) ? ['--skill', skill] : []), '--execute'];
const args = ['-d', 'Ubuntu-24.04', '-u', 'penguin', '--exec', 'python3', ...work];
const child = spawn('wsl.exe', args, { env, stdio: 'inherit', windowsHide: true });
child.on('error', error => { console.error(error.message); process.exitCode = 1; });
child.on('close', code => { process.exitCode = code ?? 1; });
