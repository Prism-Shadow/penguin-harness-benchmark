#!/usr/bin/env bash
set -euo pipefail
test -x /opt/mta-tools/clang-format-21
printf '%s  %s\n' '3d75779cdc69b06f7e39946b0e50d6ce3dccda1d766e355bf4cf507b1ae13303' /opt/mta-tools/clang-format-21 | sha256sum -c -
/opt/mta-tools/clang-format-21 --version
mta-premake5 --version
python3 - <<'PY'
import hashlib
import json
from pathlib import Path
import re
import subprocess

tools = Path("/opt/mta-tools")
record = json.loads((tools / "premake-build.json").read_text())
lock = json.loads((tools / "premake-source.lock.json").read_text())
for field in ("source_tag", "archive_sha256", "release_id", "asset_id"):
    assert record[field] == lock[field], field
assert record["source_tag"] == "v5.0.0-beta7"
assert re.fullmatch(r"[0-9a-f]{64}", record["archive_sha256"])
assert record["archive_sha256"] == record["published_sha256"]
assert record["max_build_jobs"] == 2
assert record["job_limit_method"] == "bootstrap-local getconf plus make -j2"
assert hashlib.sha256((tools / "premake5").read_bytes()).hexdigest() == record["binary_sha256"]
assert subprocess.check_output([str(tools / "premake5"), "--version"], text=True).strip() == record["version_banner"]
PY
g++ --version
python3 --version
smoke_dir="$(mktemp -d)"
trap 'rm -rf "$smoke_dir"' EXIT
cat > "$smoke_dir/premake5.lua" <<'LUA'
workspace "ToolchainSmoke"
    configurations { "Debug" }
    project "toolchain-smoke"
        kind "ConsoleApp"
        language "C++"
        cppdialect "C++23"
        targetdir "bin"
        files { "main.cpp" }
LUA
printf '%s\n' 'int main() { return 0; }' > "$smoke_dir/main.cpp"
(
    cd "$smoke_dir"
    mta-premake5 gmake2
    make -j2
    ./bin/toolchain-smoke
)
