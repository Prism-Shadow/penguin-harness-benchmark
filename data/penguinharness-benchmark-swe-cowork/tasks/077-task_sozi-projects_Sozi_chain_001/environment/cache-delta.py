"""Package only public npm cache entries changed by pinned dependency preparation."""
import hashlib,json,sys,tarfile,shutil
from pathlib import Path
root=Path('/opt/public-entry-npm-cache');manifest=Path('/opt/sozi-public-development/cache-before.json')
def hashes():
 return {str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in (root/'_cacache').rglob('*') if p.is_file()}
if sys.argv[1]=='before':
 manifest.write_text(json.dumps(hashes()))
 with tarfile.open('/opt/sozi-public-development/cache-before.tar.gz','w:gz') as archive:archive.add(root/'_cacache',arcname='_cacache')
elif sys.argv[1]=='reset':
 shutil.rmtree(root/'_cacache')
 with tarfile.open('/opt/sozi-public-development/cache-before.tar.gz') as archive:archive.extractall(root)
 assert hashes()==json.loads(manifest.read_text())
 print('Restored exact original-image npm cache before testing runtime preparation')
else:
 before=json.loads(manifest.read_text());now=hashes();changed=[name for name in now if now[name]!=before.get(name)]
 with tarfile.open('/logs/public-npm-cache-overlay.tar.gz','w:gz') as archive:
  for name in changed:archive.add(root/name,arcname=name)
 print('Public pinned npm cache delta:',len(changed),'files')

if sys.argv[1]=='after':
 with tarfile.open('/logs/public-electron-assets.tar.gz','w:gz') as archive:
  for name in ['electron-v9.2.1-linux-x64.zip','SHASUMS256.txt']:
   archive.add(Path('/opt/sozi-runtime/downloads')/name,arcname=name)
