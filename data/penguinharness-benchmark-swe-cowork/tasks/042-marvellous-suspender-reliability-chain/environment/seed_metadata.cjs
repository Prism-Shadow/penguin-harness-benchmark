// Build a bounded, frozen npm catalog from authenticated installed archives.
// These are ordinary upstream package manifests, never task source or answers.
const fs = require('node:fs');
const path = require('node:path');
const { execFileSync } = require('node:child_process');
const npmRoot = path.join(execFileSync('npm', ['root', '-g'], {encoding:'utf8'}).trim(), 'npm');
const cacache = require(require.resolve('cacache', {paths:[npmRoot]}));
const semver = require(require.resolve('semver', {paths:[npmRoot]}));
const [cache, ...projects] = process.argv.slice(2);
const documents = new Map();
const archives = new Map();
for (const project of projects) {
  const lock = JSON.parse(fs.readFileSync(path.join(project, 'package-lock.json')));
  for (const [relative, locked] of Object.entries(lock.packages)) {
    if (!relative) continue;
    const manifest = JSON.parse(fs.readFileSync(path.join(project, relative, 'package.json')));
    if (manifest.version !== locked.version) throw new Error('Archive version mismatch: ' + relative);
    manifest.dist = {tarball:locked.resolved, integrity:locked.integrity};
    archives.set(locked.resolved, locked.integrity);
    let document = documents.get(manifest.name);
    if (!document) documents.set(manifest.name, document = {name:manifest.name, versions:{}, 'dist-tags':{}});
    document.versions[manifest.version] = manifest;
  }
}
(async () => {
  for (const document of documents.values()) {
    document['dist-tags'].latest = Object.keys(document.versions).sort(semver.rcompare)[0];
    const url = 'https://registry.npmjs.org/' + document.name.replace('/', '%2f');
    await cacache.put(path.join(cache, '_cacache'), 'make-fetch-happen:request-cache:' + url,
      JSON.stringify(document), {metadata:{time:1, url,
        reqHeaders:{accept:'application/json'},
        resHeaders:{'content-type':'application/json', 'cache-control':'max-age=0'},
        options:{compress:true}}});
  }
  // npm lockfiles may omit the optional integrity field. In that valid case,
  // npm fetches the locked archive URL instead of looking it up by digest.
  // Seed its ordinary HTTP cache record from the same authenticated bytes.
  for (const [url, integrity] of archives) {
    const content = await cacache.get.byDigest(path.join(cache, '_cacache'), integrity);
    await cacache.put(path.join(cache, '_cacache'), 'make-fetch-happen:request-cache:' + url,
      content, {integrity, metadata:{time:1, url, reqHeaders:{},
        resHeaders:{'content-type':'application/octet-stream', 'cache-control':'max-age=0'},
        options:{compress:true}}});
  }
  console.log(JSON.stringify({offline_catalog_packages:documents.size, offline_archive_urls:archives.size,
    source:'authenticated upstream archive manifests and bytes'}));
})().catch(error => {console.error(error); process.exitCode = 1;});
