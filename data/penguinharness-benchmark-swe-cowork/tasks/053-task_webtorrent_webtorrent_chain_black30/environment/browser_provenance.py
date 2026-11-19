import hashlib
import json
from pathlib import Path
import subprocess

records = []
for package, binary in [('chromium', '/usr/lib/chromium/chromium'), ('firefox-esr', '/usr/lib/firefox-esr/firefox-esr')]:
    location = Path(binary).resolve()
    with location.open('rb') as handle:
        sha = hashlib.sha256()
        for block in iter(lambda: handle.read(1048576), b''):
            sha.update(block)
    records.append({'package': package, 'binary': str(location), 'sha256': sha.hexdigest(),
                    'source': subprocess.check_output(['dpkg-query', '-W', '-f=${Package} ${Version} ${Architecture}', package], text=True)})
Path('/opt/task053-browsers/PROVENANCE.json').write_text(json.dumps({'engines': records, 'source': 'Debian apt repositories in pinned parent image'}, indent=2) + '\n')
