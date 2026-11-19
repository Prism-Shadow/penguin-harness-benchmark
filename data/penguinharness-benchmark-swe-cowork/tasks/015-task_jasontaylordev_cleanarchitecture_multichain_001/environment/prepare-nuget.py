#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import binascii
import hashlib
import json
import os
import re
import shutil
import subprocess
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path


SERVICE_INDEX = "https://api.nuget.org/v3/index.json"
SIGNATURE_INDEX = "https://api.nuget.org/v3-index/repository-signatures/5.0.0/index.json"
INPUT_SUFFIXES = {".csproj", ".props", ".targets", ".slnx"}


def restore_inputs(repository: Path) -> dict[str, str]:
    return {path.relative_to(repository).as_posix(): path.read_text(encoding="utf-8-sig")
            for path in sorted(repository.rglob("*"))
            if path.is_file() and (path.suffix in INPUT_SUFFIXES or path.name == "global.json")
            and not {"obj", "bin", "artifacts", "node_modules", ".git"}.intersection(path.parts)}


def materialize(inputs: dict[str, str], destination: Path) -> None:
    if not inputs or "CleanArchitecture.slnx" not in inputs:
        raise ValueError("missing solution restore graph")
    for relative, content in inputs.items():
        path = Path(relative)
        if path.is_absolute() or ".." in path.parts or "\\" in relative:
            raise ValueError(f"unsafe restore input: {relative}")
        if path.suffix not in INPUT_SUFFIXES and relative != "global.json":
            raise ValueError(f"not a restore input: {relative}")
        target = destination / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)


def read_public_json(url: str) -> dict:
    if url not in (SERVICE_INDEX, SIGNATURE_INDEX):
        raise ValueError("unexpected NuGet metadata endpoint")
    with urllib.request.urlopen(url, timeout=60) as response:
        content = response.read(1024 * 1024 + 1)
    if len(content) > 1024 * 1024:
        raise ValueError("oversized NuGet metadata")
    return json.loads(content)


def repository_certificates(service: dict, signatures: dict) -> list[str]:
    resources = service.get("resources", [])
    if not any(resource.get("@id") == SIGNATURE_INDEX and
               resource.get("@type") == "RepositorySignatures/5.0.0" for resource in resources):
        raise ValueError("service index does not advertise the expected signature endpoint")
    certificates = signatures.get("signingCertificates", [])
    if signatures.get("allRepositorySigned") is not True:
        raise ValueError("NuGet repository does not guarantee signed packages")
    fingerprints = sorted({certificate.get("fingerprints", {}).get("2.16.840.1.101.3.4.2.1", "")
                           for certificate in certificates})
    if not fingerprints or any(not re.fullmatch(r"[a-fA-F0-9]{64}", value) for value in fingerprints):
        raise ValueError("missing or invalid repository signing certificates")
    return fingerprints


def configuration(source: str, certificates: list[str]) -> str:
    root = ET.Element("configuration")
    sources = ET.SubElement(root, "packageSources")
    ET.SubElement(sources, "clear")
    ET.SubElement(sources, "add", key="prepared" if source != SERVICE_INDEX else "nuget.org", value=source)
    ET.SubElement(ET.SubElement(root, "fallbackPackageFolders"), "clear")
    settings = ET.SubElement(root, "config")
    ET.SubElement(settings, "add", key="signatureValidationMode", value="require")
    signers = ET.SubElement(root, "trustedSigners")
    ET.SubElement(signers, "clear")
    repository = ET.SubElement(signers, "repository", name="nuget.org", serviceIndex=SERVICE_INDEX)
    for fingerprint in certificates:
        ET.SubElement(repository, "certificate", fingerprint=fingerprint,
                      hashAlgorithm="SHA256", allowUntrustedRoot="false")
    ET.indent(root)
    return ET.tostring(root, encoding="unicode") + "\n"


def environment(packages: Path, http_cache: Path, *, offline: bool) -> dict[str, str]:
    result = os.environ.copy()
    result.update(NUGET_PACKAGES=str(packages), NUGET_HTTP_CACHE_PATH=str(http_cache),
                  DOTNET_PROCESSOR_COUNT="2", DOTNET_NUGET_SIGNATURE_VERIFICATION="true",
                  NUGET_CERT_REVOCATION_MODE="offline" if offline else "online")
    return result


def run(command: list[str], repository: Path, env: dict[str, str]) -> None:
    print("RUN", json.dumps(command), "cwd", repository, flush=True)
    subprocess.run(command, cwd=repository, env=env, check=True, timeout=1800)


def restore(repository: Path, config: Path, env: dict[str, str]) -> None:
    run(["dotnet", "restore", "CleanArchitecture.slnx", "--configfile", str(config),
         "--force", "--no-http-cache", "-p:NuGetAudit=false", "-p:RestoreDisableParallel=true",
         "-warnaserror:NU1603,NU1605,NU1801", "-m:2"], repository, env)


def resolved_graph(repository: Path) -> dict:
    graph = {}
    for path in sorted(repository.rglob("project.assets.json")):
        data = json.loads(path.read_text())
        project = Path(data["project"]["restore"]["projectPath"]).relative_to(repository).as_posix()
        graph[project] = {framework: {name: details for name, details in libraries.items()
                                     if details.get("type") == "package"}
                          for framework, libraries in data["targets"].items()}
    expected = {node.attrib["Path"] for node in ET.parse(repository / "CleanArchitecture.slnx").iter("Project")}
    if not expected or not expected <= graph.keys():
        raise ValueError(f"missing restored projects: {sorted(expected - graph.keys())}")
    return graph


def checked_hash(value: str, archive: Path, field: str) -> str:
    try:
        decoded = base64.b64decode(value, validate=True)
    except (ValueError, TypeError, binascii.Error) as error:
        raise ValueError(f"invalid NuGet {field}: {archive}") from error
    if len(decoded) != 64 or base64.b64encode(decoded).decode() != value:
        raise ValueError(f"invalid NuGet {field}: {archive}")
    return value


def package_inventory(packages: Path) -> dict[str, dict]:
    inventory = {}
    for archive in sorted(packages.glob("*/*/*.nupkg")):
        digest = base64.b64encode(hashlib.sha512(archive.read_bytes()).digest()).decode()
        checksum = Path(str(archive) + ".sha512").read_text().strip()
        metadata = json.loads((archive.parent / ".nupkg.metadata").read_text())
        if metadata.get("version") != 2:
            raise ValueError(f"unsupported NuGet metadata version: {archive}")
        payload = {}
        for path in sorted(archive.parent.rglob("*")):
            if path.is_symlink():
                raise ValueError(f"symlink in NuGet cache: {path}")
            if path.is_file() and path not in (archive, Path(str(archive) + ".sha512"), archive.parent / ".nupkg.metadata"):
                payload[path.relative_to(archive.parent).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
        inventory[archive.relative_to(packages).as_posix()] = {
            "archive_sha512": digest,
            "legacy_sha512": checked_hash(checksum, archive, "legacy SHA512"),
            "content_hash": checked_hash(metadata.get("contentHash"), archive, "content hash"),
            "metadata_version": metadata["version"],
            "payload_sha256": payload,
        }
    if not inventory:
        raise ValueError("empty verified package closure")
    return inventory


def merge_packages(source: Path, destination: Path) -> None:
    inventory = package_inventory(source)
    existing = package_inventory(destination) if any(destination.glob("*/*/*.nupkg")) else {}
    for relative, record in inventory.items():
        archive = source / relative
        target = destination / relative
        if target.exists():
            if existing.get(relative) != record:
                raise ValueError(f"conflicting package bytes or metadata: {relative}")
        else:
            shutil.copytree(archive.parent, target.parent)


def warm(baseline: Path, snapshot: Path, work: Path, packages: Path) -> None:
    work.mkdir(parents=True, exist_ok=False)
    if packages.exists() and any(packages.iterdir()):
        raise ValueError("warmup requires a fresh output cache")
    service = read_public_json(SERVICE_INDEX)
    signatures = read_public_json(SIGNATURE_INDEX)
    certificates = repository_certificates(service, signatures)
    (work / "repository-signatures.json").write_text(json.dumps(signatures, indent=2) + "\n")
    online = configuration(SERVICE_INDEX, certificates)
    snapshot_data = json.loads(snapshot.read_text())
    if snapshot_data["schema"] != "nuget-restore-graph-v1":
        raise ValueError("unknown restore snapshot schema")
    for label, inputs in (("baseline", restore_inputs(baseline)), ("target", snapshot_data["inputs"])):
        repository = work / label
        materialize(inputs, repository)
        config = repository / "NuGet.Config"
        config.write_text(online)
        cache = work / f"packages-{label}"
        env = environment(cache, work / f"http-{label}", offline=False)
        restore(repository, config, env)
        (work / f"{label}-resolved.json").write_text(json.dumps(resolved_graph(repository), sort_keys=True))
        inventory = package_inventory(cache)
        archives = [str(cache / relative) for relative in inventory]
        for start in range(0, len(archives), 16):
            run(["dotnet", "nuget", "verify", "--all", *archives[start:start + 16]], repository, env)
        if package_inventory(cache) != inventory:
            raise ValueError(f"package cache changed during signature verification: {label}")
        (work / f"{label}-inventory.json").write_text(json.dumps(inventory, sort_keys=True))
        merge_packages(cache, packages)
    packages.parent.mkdir(parents=True, exist_ok=True)
    (packages.parent / "NuGet.Config").write_text(configuration(str(packages), certificates))
    (packages.parent / "integrity.json").write_text(json.dumps(package_inventory(packages), indent=2) + "\n")
    (packages.parent / "repository-signatures.json").write_text(json.dumps(signatures, indent=2) + "\n")
    print("PASS independently restored and signature-verified both complete project graphs", flush=True)


def check_offline(work: Path, packages: Path) -> None:
    expected = json.loads((packages.parent / "integrity.json").read_text())
    if package_inventory(packages) != expected:
        raise ValueError("prepared closure changed after signature verification")
    config = packages.parent / "NuGet.Config"
    for label in ("baseline", "target"):
        repository = work / f"offline-{label}"
        materialize(restore_inputs(work / label), repository)
        local_config = repository / "NuGet.Config"
        local_config.write_bytes(config.read_bytes())
        cache = work / f"offline-packages-{label}"
        http_cache = work / f"offline-http-{label}"
        if cache.exists() or http_cache.exists():
            raise ValueError("offline check requires empty package and HTTP caches")
        env = environment(cache, http_cache, offline=True)
        restore(repository, local_config, env)
        expected_graph = json.loads((work / f"{label}-resolved.json").read_text())
        if resolved_graph(repository) != expected_graph:
            raise ValueError(f"offline dependency resolution drift: {label}")
        inventory = package_inventory(cache)
        expected_inventory = json.loads((work / f"{label}-inventory.json").read_text())
        if inventory != expected_inventory:
            differences = sorted(relative for relative in inventory.keys() | expected_inventory.keys()
                                 if inventory.get(relative) != expected_inventory.get(relative))
            raise ValueError(f"offline package bytes or metadata differ: {label}: {differences}")
        for relative, record in inventory.items():
            if expected.get(relative) != record:
                raise ValueError(f"offline package absent from verified union: {relative}")
        print(f"PASS {label}: empty-cache offline restore matches every online project dependency, "
              f"all {len(inventory)} packages, independent hash records and extracted payloads", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("warm", "check"))
    parser.add_argument("--baseline", type=Path, default=Path("/workspace"))
    parser.add_argument("--snapshot", type=Path, default=Path("/opt/offline-target/dotnet-graph.json"))
    parser.add_argument("--work", type=Path, default=Path("/opt/nuget-preparation"))
    parser.add_argument("--packages", type=Path, default=Path("/opt/nuget/packages"))
    args = parser.parse_args()
    if args.mode == "warm":
        warm(args.baseline, args.snapshot, args.work, args.packages)
    else:
        check_offline(args.work, args.packages)


if __name__ == "__main__":
    main()
