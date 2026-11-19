"""Pin all Docker COPY inputs; the public release parent supplies offline tools."""
import hashlib
import json
from pathlib import Path
root=Path(__file__).resolve().parents[1]
environment=root/'environment'
selected=[environment/n for n in ('Dockerfile','Dockerfile.workplace','.dockerignore','sanitize_repository.py','bazel_offline.py','check_runtime.py','task_README.md','CONTRACT.md','OFFLINE_RUNTIME.md')]
selected += [environment/n for n in ('OFFLINE_BUILD.md','prepare_offline.py','install_offline_closure.py','sync_runtime_manifest.py','workplace_mcp.py')]
selected += [p for p in (environment/'workplace/authoring').rglob('*') if p.is_file() and '__pycache__' not in p.parts]
selected += [environment/'workplace/harness/config/workplace.json']
selected += [p for p in (environment/'workplace').iterdir() if p.is_file()]
manifest={'schema':'cowork-image-build-context-v1','files':{str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(selected)}}
(environment/'BUILD_CONTEXT.json').write_text(json.dumps(manifest,indent=2)+'\n')
print('BUILD_CONTEXT_PINNED',len(selected),'files')
