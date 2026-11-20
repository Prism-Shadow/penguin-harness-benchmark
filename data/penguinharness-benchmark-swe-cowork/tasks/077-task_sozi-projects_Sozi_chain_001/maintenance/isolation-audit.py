"""Hash visible files and archive members against independently supplied forbidden content."""
import hashlib
from pathlib import Path
import tarfile
import zipfile


def audit(roots, forbidden):
    roots=[Path(p).resolve() for p in roots]
    records,violations,errors=[],[],[]
    def record(name,data):
        digest=hashlib.sha256(data).hexdigest()
        row={'path':str(name),'sha256':digest,'bytes':len(data)}
        records.append(row)
        if digest in forbidden:violations.append(dict(row,reason=forbidden[digest]))
    for root in roots:
        if not root.exists():
            errors.append('missing root: '+str(root));continue
        for file in ([root] if root.is_file() else root.rglob('*')):
            try:
                if file.is_symlink():
                    if not any(file.resolve().is_relative_to(p) for p in roots):errors.append('unscanned symlink: '+str(file))
                    continue
                if not file.is_file():continue
                data=file.read_bytes();record(file,data)
                if zipfile.is_zipfile(file):
                    with zipfile.ZipFile(file) as archive:
                        for item in archive.infolist():
                            if not item.is_dir():record(str(file)+'!'+item.filename,archive.read(item))
                elif file.suffix in ('.tgz','.gz','.tar') and tarfile.is_tarfile(file):
                    with tarfile.open(file) as archive:
                        for item in archive:
                            if item.isfile():record(str(file)+'!'+item.name,archive.extractfile(item).read())
            except (OSError,ValueError,zipfile.BadZipFile,tarfile.TarError) as error:
                errors.append(str(file)+': '+str(error))
    return records,violations,errors
