"""Acquire the project's pinned public terraform-docs tool and official checksum."""
import hashlib
import base64
import json
from pathlib import Path
import sys
import time
import urllib.request

target = Path(sys.argv[1])
target.mkdir(parents=True, exist_ok=True)
base = 'https://github.com/terraform-docs/terraform-docs/releases/download/v0.16.0/'
filename = 'terraform-docs-v0.16.0-linux-amd64.tar.gz'
checksums_url = base + 'terraform-docs-v0.16.0.sha256sum'
def get(url, limit):
    for attempt in range(3):
        try:
            with urllib.request.urlopen(url, timeout=40) as response:
                data = response.read(limit + 1)
            assert len(data) <= limit
            return data
        except OSError:
            if attempt == 2:
                raise
            time.sleep(attempt + 1)
checksums = get(checksums_url, 128 * 1024)
expected = next(line.split()[0] for line in checksums.decode().splitlines() if line.split()[-1].lstrip('*') == filename)
data = get(base + filename, 32 * 1024 * 1024)
actual = hashlib.sha256(data).hexdigest()
assert actual == expected, (actual, expected)
(target / filename).write_bytes(data)
(target / 'terraform-docs-v0.16.0.sha256sum').write_bytes(checksums)
(target / 'tool-lock.json').write_text(json.dumps(dict(name='terraform-docs', version='0.16.0', filename=filename,
    url=base + filename, sha256=actual, verification='official-release-sha256sum', checksums_url=checksums_url,
    checksums_sha256=hashlib.sha256(checksums).hexdigest()), indent=2) + '\n')
print('TERRAFORM_DOCS_ACQUIRED', filename, len(data), actual)

# Optional stdout transport for the trusted build broker; only these public inputs.
if "--emit-base64" in sys.argv[2:]:
    payload = {name: base64.b64encode((target / name).read_bytes()).decode() for name in [filename, "terraform-docs-v0.16.0.sha256sum", "tool-lock.json"]}
    print("CODEGEN_TOOL_INPUTS_JSON " + json.dumps(payload), flush=True)
