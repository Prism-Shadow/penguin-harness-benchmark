#!/usr/bin/env python3
"""Hash the complete explicit candidate build contexts for portable packaging."""
import hashlib,json
from pathlib import Path
root=Path(__file__).resolve().parents[1]
paths=[root/'environment/Dockerfile',root/'environment/.dockerignore',root/'environment/baseline.bundle',root/'environment/install_development_bundle.sh']
workplace=root/'environment/workplace-service'
paths += [workplace/name for name in ['Dockerfile','.dockerignore','workplace-sidecar','harbor_dynamic_colleague_adapter.py','runtime_daemon.py','semantic_colleague.py','colleague_availability.py']]
paths += [p for p in (workplace/'original').rglob('*') if p.is_file()]
value={'schema':'cowork-build-inputs-v1','files':{str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(paths)}}
(root/'environment/build-inputs.json').write_text(json.dumps(value,indent=2)+'\n')
print('Recorded',len(paths),'complete build inputs')
