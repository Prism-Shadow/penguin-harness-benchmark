/** Rebuild locked JavaScript dependencies without changing production manifests. */
import {cpSync, existsSync, mkdtempSync, readFileSync, renameSync, rmSync, writeFileSync} from 'node:fs';
import {join} from 'node:path';
import {tmpdir} from 'node:os';
import {spawnSync} from 'node:child_process';
export function registryLock(lock) {
  const copy = structuredClone(lock);
  for (const entry of Object.values(copy.packages || {})) {
    if (typeof entry.resolved === 'string' && entry.resolved.startsWith('https://mirrors.tencent.com/npm/')) {
      if (!entry.integrity) throw new Error('missing locked integrity');
      entry.resolved = entry.resolved.replace('https://mirrors.tencent.com/npm/', 'https://registry.npmjs.org/');
    }
  }
  return copy;
}
export function installProject(project, staging) {
  const destination = join(project, 'node_modules');
  if (existsSync(destination)) throw new Error('expected clean dependency destination');
  const temporary = mkdtempSync(join(staging, 'project-'));
  try {
    cpSync(join(project, 'package.json'), join(temporary, 'package.json'));
    const lock = registryLock(JSON.parse(readFileSync(join(project, 'package-lock.json'), 'utf8')));
    writeFileSync(join(temporary, 'package-lock.json'), JSON.stringify(lock));
    const result = spawnSync('npm', ['ci', '--ignore-scripts', '--no-audit', '--no-fund', '--cache='+join(staging,'cache'),
      '--maxsockets=2', '--fetch-retries=2', '--fetch-timeout=20000', '--loglevel=error'], {cwd:temporary,encoding:'utf8'});
    if (result.error || result.status !== 0) throw new Error('npm ci failed: '+(result.error || result.stderr || result.stdout));
    try { renameSync(join(temporary,'node_modules'), destination); }
    catch (error) {
      if (error.code !== 'EXDEV') throw error;
      cpSync(join(temporary,'node_modules'), destination, {recursive:true,errorOnExist:true});
    }
  } catch (error) { rmSync(destination,{recursive:true,force:true}); throw error; }
  finally { rmSync(temporary,{recursive:true,force:true}); }
}
export function installDependencies(workspace) {
  const staging = mkdtempSync(join(tmpdir(),'puerts-dependencies-'));
  try { for (const project of ['agent_proj','mcp_proj']) installProject(join(workspace,'unity',project),staging); }
  finally { rmSync(staging,{recursive:true,force:true}); }
}
