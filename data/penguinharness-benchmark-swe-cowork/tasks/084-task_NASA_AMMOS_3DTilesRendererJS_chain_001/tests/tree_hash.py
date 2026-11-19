from __future__ import annotations

import hashlib
from pathlib import Path
import sys

root = Path(sys.argv[1] if len(sys.argv) > 1 else '.')
excluded = {'node_modules', 'build', 'dist', '.git'}
digest = hashlib.sha256()
for path in sorted(p for p in root.rglob('*') if p.is_file() and not any(part in excluded for part in p.parts)):
    relative = path.relative_to(root).as_posix().encode()
    data = path.read_bytes()
    digest.update(len(relative).to_bytes(8, 'big'))
    digest.update(relative)
    digest.update(len(data).to_bytes(8, 'big'))
    digest.update(data)
print(digest.hexdigest())
