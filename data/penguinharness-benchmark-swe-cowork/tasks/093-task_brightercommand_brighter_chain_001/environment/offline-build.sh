#!/usr/bin/env bash
set -Eeuo pipefail
repo=${REPO_DIR:-/app/code}
assets=${SEGPIPE_ASSETS_ROOT:-/opt/segpipe-restore-assets}
mode=${1:-focused}
preflight_only=0
if [ "$mode" = preflight ]; then
  mode=${2:-focused}
  preflight_only=1
fi
case "$mode" in
  focused|full|smoke) ;;
  *) echo 'usage: offline-build.sh focused|full|smoke|preflight [focused|full|smoke]' >&2; exit 64 ;;
esac
export DOTNET_CLI_TELEMETRY_OPTOUT=1 DOTNET_NOLOGO=1 NUGET_XMLDOC_MODE=skip
export NUGET_PACKAGES=${NUGET_PACKAGES:-/root/.nuget/packages}
export DOTNET_PROCESSOR_COUNT=2
root=$(cd -- "$(dirname -- "$0")" && pwd)
profile=${SEGPIPE_BUILD_PROFILE:-$root/offline-net10.targets}
python3 "$root/offline-preflight.py" --repo "$repo" --assets "$assets" --packages "$NUGET_PACKAGES" \
  --profile "$profile" --focused-file "$root/focused-projects.txt" --mode "$mode"
if [ "$preflight_only" = 1 ]; then
  exit 0
fi
if [ "$mode" = smoke ]; then
  destination="$repo/.task-build/public-smoke"
  mkdir -p "$destination"
  cp "$root/public-smoke/Smoke.csproj" "$root/public-smoke/Program.cs" "$destination/"
  dotnet restore "$destination/Smoke.csproj" --source "$NUGET_PACKAGES" --disable-parallel -p:NuGetAudit=false
  dotnet build "$destination/Smoke.csproj" --no-restore -c Release -m:2
  dotnet "$destination/bin/Release/net10.0/Smoke.dll"
  exit $?
fi
mkdir -p "$repo/.task-build"
solution="$repo/.task-build/$mode.slnx"
python3 - "$repo" "$root/focused-projects.txt" "$mode" "$solution" <<'PY'
from pathlib import Path
import sys
import xml.etree.ElementTree as ET
repo, focused, mode, solution = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3], Path(sys.argv[4])
if mode == 'full':
    projects = sorted(path.relative_to(repo).as_posix() for path in (repo / 'src').rglob('*.csproj'))
    (repo / '.task-build/all-source-projects.txt').write_text('\n'.join(projects) + '\n')
else:
    projects = [line.strip() for line in focused.read_text().splitlines() if line.strip() and not line.lstrip().startswith('#')]
if not projects or len(projects) != len(set(projects)):
    raise SystemExit('empty or duplicate source project selection')
document = ET.Element('Solution')
for relative in projects:
    project = (repo / relative).resolve(strict=True)
    project.relative_to(repo.resolve())
    ET.SubElement(document, 'Project', {'Path': str(project)})
ET.ElementTree(document).write(solution, encoding='utf-8', xml_declaration=True)
PY
# Evaluate the original project graph and framework-conditioned version pins.
# Offline restore recreates current assets instead of copying stale BASE assets
# over GOLD, or forcing projects without net10 support onto net10.
dotnet restore "$solution" --source "$NUGET_PACKAGES" --disable-parallel --force \
  -p:NuGetAudit=false -p:NoWarn=NU1510
dotnet build "$solution" --no-restore -c Release -m:2 -p:NuGetAudit=false -p:NoWarn=NU1510
