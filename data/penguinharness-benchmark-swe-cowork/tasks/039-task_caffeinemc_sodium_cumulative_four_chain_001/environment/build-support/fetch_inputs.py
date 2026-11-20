"""Fetch immutable, checksummed public build inputs; never downloads Sodium."""
from pathlib import Path
import hashlib, io, tarfile, urllib.request, zipfile, time

def fetch(url, sha):
    for attempt in range(4):
        try:
            with urllib.request.urlopen(url, timeout=180) as response:
                data = response.read()
            if hashlib.sha256(data).hexdigest() != sha:
                raise ValueError('checksum mismatch: ' + url)
            print('VERIFIED_INPUT', url, sha, len(data), flush=True)
            return data
        except (OSError, TimeoutError):
            if attempt == 3: raise
            time.sleep(3 * (attempt + 1))

for version, sha in {
    '8.10.2': '31c55713e40233a8303827ceb42ca48a47267a0ad4bab9177123121e71524c26',
    '8.7': '544c35d6bd849ae8a5ed0bcea39ba677dc40f49df7d1835561582da2009b961d',
}.items():
    data = fetch(f'https://downloads.gradle.org/distributions/gradle-{version}-bin.zip', sha)
    root = Path('/opt/gradle'); root.mkdir(exist_ok=True)
    with zipfile.ZipFile(io.BytesIO(data)) as archive: archive.extractall(root)
    (root / f'gradle-{version}/bin/gradle').chmod(0o755)

commit = 'fb509f4d2e545953987729633970f38a852791f0'
data = fetch('https://codeload.github.com/IMS212/ForgifiedFabricAPI/tar.gz/' + commit,
             '394ad0bfd3ce0650b80d934ea9d72a57cffef75019cf4c18e8905d4a126e37de')
root = Path('/opt/fapi-source'); root.mkdir()
with tarfile.open(fileobj=io.BytesIO(data), mode='r:gz') as archive:
    for member in archive.getmembers():
        parts = Path(member.name).parts
        if len(parts) < 2: continue
        member.name = str(Path(*parts[1:]))
        archive.extract(member, root, filter='data')
# Source builds have an explicit, honest version: never masquerade as the old
# inaccessible Maven artifact. No Sodium sources are used in these dependencies.
p = root / 'build.gradle.kts'
text = p.read_text().replace('$version+nogit', '$version+repair.fb509f4d').replace('version "0.5.+"', 'version "0.5.2"')
# The upstream aggregate mod adds every child to its own api configuration in
# afterEvaluate, after Loom has already resolved it during a clean setup. We
# publish the four real child modules, not that unused aggregate distribution.
aggregate = '''dependencies {
\tafterEvaluate {
\t\tsubprojects.forEach { proj ->
\t\t\tif (proj.name in META_PROJECTS) {
\t\t\t\treturn@forEach
\t\t\t}

\t\t\tinclude(api(project(proj.path, "namedElements"))!!)
\t\t}
\t}
}'''
if text.count(aggregate) != 1:
    raise RuntimeError('FFAPI aggregate build script changed')
p.write_text(text.replace(aggregate, ''))
