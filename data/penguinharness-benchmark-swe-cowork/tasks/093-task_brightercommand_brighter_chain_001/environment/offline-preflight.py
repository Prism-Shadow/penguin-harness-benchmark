#!/usr/bin/env python3
import argparse
import json
from pathlib import Path
import re
import sys
import xml.etree.ElementTree as ET


def local_name(tag):
    return tag.rsplit('}', 1)[-1]


def project_files(repo, mode, focused_file):
    if mode == 'focused':
        names = [line.strip() for line in focused_file.read_text().splitlines()
                 if line.strip() and not line.lstrip().startswith('#')]
        return [repo / name for name in names]
    if mode == 'smoke':
        return [repo / 'src/Paramore.Brighter/Paramore.Brighter.csproj']
    return sorted((repo / 'src').rglob('*.csproj'))


def package_ids(project_file):
    root = ET.parse(project_file).getroot()
    result = []
    for element in root.iter():
        if local_name(element.tag) == 'PackageReference' and element.get('Include'):
            result.append(element.get('Include'))
    return result


def package_libraries(asset_file):
    data = json.loads(asset_file.read_text())
    return [key.rsplit('/', 1) for key, value in data.get('libraries', {}).items()
            if value.get('type') == 'package' and '/' in key]


def framework_replacements(profile_file):
    text = profile_file.read_text()
    if 'Microsoft.AspNetCore.App' not in text:
        return set()
    if 'Paramore.Brighter.Extensions.DependencyInjection' not in text:
        return set()
    removed = set()
    match = re.search(r'<PackageReference\s+Remove="([^"]+)"', text)
    if match:
        removed.update(item.strip().lower() for item in match.group(1).split(';'))
    return removed


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--repo', type=Path, required=True)
    parser.add_argument('--assets', type=Path, required=True)
    parser.add_argument('--packages', type=Path, required=True)
    parser.add_argument('--profile', type=Path, required=True)
    parser.add_argument('--focused-file', type=Path, required=True)
    parser.add_argument('--mode', choices=('focused', 'full', 'smoke'), required=True)
    args = parser.parse_args()

    problems = []
    projects = project_files(args.repo, args.mode, args.focused_file)
    if args.profile.is_file():
        replacements = framework_replacements(args.profile)
    else:
        replacements = set()
        problems.append(f'missing build profile: {args.profile}')
    checked = 0
    asset_count = 0
    package_count = 0
    unresolved_projects = []
    for project in projects:
        checked += 1
        if not project.is_file():
            problems.append(f'missing source project: {project.relative_to(args.repo)}')
            continue
        relative = project.relative_to(args.repo)
        asset_file = args.assets / relative.parent / 'obj/project.assets.json'
        if asset_file.is_file():
            asset_count += 1
            try:
                libraries = package_libraries(asset_file)
            except (OSError, ValueError, json.JSONDecodeError) as error:
                problems.append(f'invalid restore asset {asset_file}: {error}')
                continue
            for package_name, version in libraries:
                package_count += 1
                package_path = args.packages / package_name.lower() / version
                try:
                    available = package_path.is_dir()
                except OSError:
                    available = False
                if not available:
                    problems.append(f'missing cached package {package_name}/{version} for {relative}')
            continue
        unresolved_projects.append(str(relative))
        for package_name in package_ids(project):
            if (project.stem == 'Paramore.Brighter.Extensions.DependencyInjection'
                    and package_name.lower() in replacements):
                continue
            package_dir = args.packages / package_name.lower()
            try:
                available = package_dir.is_dir()
            except OSError:
                available = False
            if not available:
                problems.append(f'missing package cache {package_name} for {relative}')

    report = {
        'schema': 'brighter-offline-preflight-v1',
        'mode': args.mode,
        'projects_checked': checked,
        'projects_with_restore_assets': asset_count,
        'package_entries_checked': package_count,
        'validation_scope': 'static cache presence only; not MSBuild evaluation or SDK/build validation',
        'projects_without_restore_assets': unresolved_projects,
        'framework_replacements': sorted(replacements),
        'problems': problems,
        'status': 'ok' if not problems else 'missing_offline_inputs',
    }
    print(json.dumps(report, sort_keys=True))
    if problems:
        print('Offline preflight requires dependency hydration before this mode can run.', file=sys.stderr)
        return 78
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
