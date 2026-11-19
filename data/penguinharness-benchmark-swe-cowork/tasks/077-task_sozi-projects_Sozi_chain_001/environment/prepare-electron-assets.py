"""Recover or fetch checksum-pinned stock Electron assets for offline packaging."""
import importlib.util,shutil
from pathlib import Path
spec=importlib.util.spec_from_file_location('download','/usr/local/lib/sozi-install-render-runtime.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
cache=Path('/opt/sozi-runtime/downloads');cache.mkdir(parents=True,exist_ok=True)
for name in module.PINNED_DIGESTS:
 if module.verified(cache/name,name):continue
 for root in [Path('/opt'),Path('/var/cache')]:
  for source in root.rglob(name):
   if module.verified(source,name):shutil.copyfile(source,cache/name);break
  if module.verified(cache/name,name):break
module.prepare(cache,timeout=180,attempts=3)
