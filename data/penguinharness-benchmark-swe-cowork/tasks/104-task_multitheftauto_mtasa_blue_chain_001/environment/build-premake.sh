#!/usr/bin/env bash
set -euo pipefail
source_dir="$(realpath -m -- "$1")"
output_dir="$(realpath -m -- "$2")"
test ! -e "$source_dir"
script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
python3 "$script_dir/fetch-premake-source.py" "$source_dir"
python3 - "$source_dir" "$script_dir/premake-source.lock.json" <<'PY'
import json
from pathlib import Path
import sys

record = json.loads((Path(sys.argv[1]) / ".source-provenance.json").read_text())
lock = json.loads(Path(sys.argv[2]).read_text())
for field in ("source_tag", "archive_sha256", "release_id", "asset_id"):
    if record.get(field) != lock[field]:
        raise SystemExit("Premake source lock mismatch: " + field)
if record.get("published_sha256") != lock["archive_sha256"]:
    raise SystemExit("Premake published digest mismatch")
PY
export PREMAKE_SYSTEM_GETCONF="$(command -v getconf)"
mkdir "$source_dir/.bootstrap-tools"
cat > "$source_dir/.bootstrap-tools/getconf" <<'SH'
#!/usr/bin/env sh
set -eu
if [ "$#" = 1 ] && [ "$1" = _NPROCESSORS_ONLN ]; then
    printf '2\n'
else
    exec "$PREMAKE_SYSTEM_GETCONF" "$@"
fi
SH
chmod 0555 "$source_dir/.bootstrap-tools/getconf"
(
    cd "$source_dir"
    export PATH="$source_dir/.bootstrap-tools:$PATH"
    export MAKEFLAGS=-j2
    make -j2 -f Bootstrap.mak linux
)
mkdir -p "$output_dir"
install -m 0555 "$source_dir/bin/release/premake5" "$output_dir/premake5"
install -m 0444 "$script_dir/premake-source.lock.json" "$output_dir/premake-source.lock.json"
python3 - "$source_dir" "$output_dir" <<'PY'
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

source = Path(sys.argv[1])
output = Path(sys.argv[2])
record = json.loads((source / ".source-provenance.json").read_text())
lock = json.loads((output / "premake-source.lock.json").read_text())
banner = subprocess.check_output([str(output / "premake5"), "--version"], text=True).strip()
print("Built Premake banner: " + banner, flush=True)
pattern = r"premake5 \(Premake Build Script Generator\) " + re.escape(lock["version_family"]) + r"(?:-[0-9A-Za-z.-]+)?"
if not re.fullmatch(pattern, banner):
    raise SystemExit("Invalid Premake version banner for locked source")
record.update({
    "binary_sha256": hashlib.sha256((output / "premake5").read_bytes()).hexdigest(),
    "compiler": subprocess.check_output(["cc", "--version"], text=True).splitlines()[0],
    "max_build_jobs": 2,
    "job_limit_method": "bootstrap-local getconf plus make -j2",
    "version_banner": banner,
})
(output / "premake-build.json").write_text(json.dumps(record, indent=2) + "\n")
PY
