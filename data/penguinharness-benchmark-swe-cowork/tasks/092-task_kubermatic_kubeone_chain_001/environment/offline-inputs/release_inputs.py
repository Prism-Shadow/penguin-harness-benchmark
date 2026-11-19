"""Trusted-builder import and network-free regeneration of public upstream inputs."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tarfile


SOURCES = {
    "cilium-chart-1.15.2": ("https://helm.cilium.io/cilium-1.15.2.tgz", "cilium-1.15.2.tgz"),
    "calico-vxlan-v3.27.2": ("https://raw.githubusercontent.com/projectcalico/calico/v3.27.2/manifests/calico-vxlan.yaml", "calico-vxlan-v3.27.2.yaml"),
    "canal-v3.27.2": ("https://raw.githubusercontent.com/projectcalico/calico/v3.27.2/manifests/canal.yaml", "canal-v3.27.2.yaml"),
}
ADDONS = {"cni-cilium": "cilium.yaml", "calico-vxlan": "calico-vxlan.yaml", "cni-canal": "canal.yaml", "ccm-azure": "ccm-azure.yaml", "csi-azuredisk": "csi-azuredisk.yaml", "csi-vmware-cloud-director": "driver.yaml"}
MAX_BYTES = 32 * 1024 * 1024


def digest(path):
    if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_BYTES:
        raise ValueError(f"not a bounded regular input: {path}")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def chart_members(archive, chart_name="cilium", chart_version="1.15.2"):
    members = archive.getmembers()
    if len(members) > 4096 or sum(member.size for member in members) > MAX_BYTES:
        raise ValueError("chart exceeds extraction limits")
    seen = set()
    for member in members:
        name = Path(member.name)
        if (name.is_absolute() or ".." in name.parts or not name.parts or
                name.parts[0] != chart_name or not (member.isdir() or member.isfile()) or
                name.as_posix() in seen):
            raise ValueError(f"unsafe chart member: {member.name}")
        seen.add(name.as_posix())
    metadata = archive.extractfile(chart_name + "/Chart.yaml").read().decode()
    for key, value in (("name", chart_name), ("version", chart_version)):
        if not re.search(rf"^{key}:\s*['\"]?{re.escape(value)}['\"]?\s*$", metadata, re.M):
            raise ValueError(f"unexpected chart {key}")
    return members


def verify(inputs):
    lock_path = inputs / "resolved-lock.json"
    if not lock_path.exists() and not lock_path.is_symlink():
        lock_path = inputs / "image-lock.json"
    digest(lock_path)
    lock = json.loads(lock_path.read_text())
    if lock_path.name == "resolved-lock.json":
        requirements = json.loads((inputs / "image-lock.json").read_text())
        if any(lock.get(key) != requirements.get(key) for key in ("revision", "images")):
            raise ValueError("resolved inputs do not match the published requirements revision")
    entries = {entry["id"]: entry for entry in lock["upstream_inputs"]}
    if len(entries) != len(lock["upstream_inputs"]) or set(entries) != set(SOURCES):
        raise ValueError("upstream closure does not list exactly the three required inputs")
    if lock_path.name == "resolved-lock.json":
        for required in requirements["upstream_inputs"]:
            if required.get("status") == "available" and any(
                    required.get(key) != entries[required["id"]].get(key)
                    for key in ("sha256", "provenance_sha256")):
                raise ValueError("resolved inputs do not match preapproved source checksums")
    for identifier, (url, filename) in SOURCES.items():
        entry = entries[identifier]
        if entry.get("status") != "available" or not entry.get("sha256"):
            raise ValueError(f"missing authentic upstream input: {identifier}")
        if entry.get("url") != url or entry.get("path") != filename:
            raise ValueError(f"unexpected source or entrypoint: {identifier}")
        if digest(inputs / filename) != entry["sha256"]:
            raise ValueError(f"upstream checksum mismatch: {identifier}")
        receipt = inputs / f"{identifier}.provenance.json"
        if digest(receipt) != entry.get("provenance_sha256"):
            raise ValueError(f"provenance checksum mismatch: {identifier}")
        provenance = json.loads(receipt.read_text())
        if provenance["url"] != url or provenance["sha256"] != entry["sha256"] or not provenance["verification"]:
            raise ValueError(f"inconsistent provenance: {identifier}")
    with tarfile.open(inputs / SOURCES["cilium-chart-1.15.2"][1]) as archive:
        chart_members(archive)
    additional = inputs / "additional-lock.json"
    if additional.exists():
        for entry in json.loads(additional.read_text()):
            if digest(inputs / entry["path"]) != entry["sha256"] or not entry.get("verification"):
                raise ValueError("additional public input checksum/provenance mismatch: " + entry["id"])
            entries[entry["id"]] = entry
    return entries


def import_input(inputs, identifier, source, expected, provenance_path):
    if not re.fullmatch(r"[0-9a-f]{64}", expected) or digest(source) != expected:
        raise ValueError("input does not match the independently approved SHA256")
    url, filename = SOURCES[identifier]
    provenance = json.loads(provenance_path.read_text())
    if provenance.get("url") != url or provenance.get("sha256") != expected or not provenance.get("verification"):
        raise ValueError("provide a source/checksum verification receipt, not just a computed checksum")
    if identifier == "cilium-chart-1.15.2":
        with tarfile.open(source) as archive:
            chart_members(archive)
    lock_path = inputs / "image-lock.json"
    lock = json.loads(lock_path.read_text())
    entry = next(entry for entry in lock["upstream_inputs"] if entry["id"] == identifier)
    destination = inputs / filename
    receipt = inputs / f"{identifier}.provenance.json"
    if destination.exists() or destination.is_symlink() or receipt.exists() or receipt.is_symlink():
        raise ValueError("refusing to overwrite a published input or provenance receipt")
    shutil.copyfile(source, destination)
    shutil.copyfile(provenance_path, receipt)
    entry.update(url=url, path=filename, status="available", sha256=expected,
                 provenance_sha256=digest(receipt))
    lock_path.write_text(json.dumps(lock, indent=2) + "\n")


def render(inputs, repo, output, selected=None):
    entries = verify(inputs)
    import yaml

    if output.exists():
        raise ValueError("generation requires a fresh output directory")
    output.mkdir(parents=True)
    environment = os.environ.copy()
    environment.update(HELM_CACHE_HOME=str(output / "helm-cache"),
                       HELM_CONFIG_HOME=str(output / "helm-config"),
                       HELM_DATA_HOME=str(output / "helm-data"), GOMAXPROCS="2")
    versions = {}
    for command in (["helm", "version", "--short"], ["kustomize", "version"]):
        versions[command[0]] = subprocess.check_output(command, env=environment, text=True).strip()
    for addon, filename in ADDONS.items():
        if selected and addon not in selected: continue
        source = repo / "addons" / addon
        stage = output / "sources" / addon
        stage.mkdir(parents=True)
        for path in source.rglob("*"):
            if path.is_symlink():
                raise ValueError(f"symlink in regeneration source: {path}")
            if path.is_file():
                digest(path)
                target = stage / path.relative_to(source)
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(path, target)
        # Follow the reachable Kustomize graph. A nested base/component or a
        # different patch-file layout is a valid production implementation.
        charts_by_addon = {
            "cni-cilium": ("cilium", "1.15.2", "cilium-chart-1.15.2"),
            "ccm-azure": ("cloud-provider-azure", "1.29.0+20240201", "cloud-provider-azure"),
            "csi-azuredisk": ("azuredisk-csi-driver", "v1.29.5", "azuredisk-csi-driver"),
        }
        sources = {entry["url"]: entry for entry in entries.values()}
        sources.update({entry["reference"]: entry for entry in entries.values() if "reference" in entry})
        used, visited = set(), set()
        def inside(path):
            path = path.resolve()
            if not path.is_relative_to(stage.resolve()):
                raise ValueError("generation source escapes addon: " + str(path))
            return path
        def prepare(directory):
            directory = inside(directory)
            if directory in visited: return
            visited.add(directory)
            configs = [directory / name for name in ("Kustomization", "kustomization.yaml", "kustomization.yml") if (directory / name).is_file()]
            if len(configs) != 1: raise ValueError(f"expected one Kustomization in {directory}")
            config = yaml.safe_load(configs[0].read_text())
            for chart in config.get("helmCharts", []):
                expected = charts_by_addon.get(addon)
                if not expected or (chart.get("name"), str(chart.get("version"))) != expected[:2]:
                    raise ValueError(f"unavailable authenticated chart for {addon}: {chart.get('name')} {chart.get('version')}")
                name, version, identifier = expected
                chart_home = config.get("helmGlobals", {}).get("chartHome", "charts")
                chart_root = inside(directory / chart_home / (name + "-" + version))
                if chart_root.exists(): shutil.rmtree(chart_root)
                chart_root.mkdir(parents=True)
                with tarfile.open(inputs / entries[identifier]["path"]) as archive:
                    archive.extractall(chart_root, members=chart_members(archive, name, version))
                used.add(identifier)
            for field in ("resources", "bases", "components"):
                replaced = []
                for resource in config.get(field, []):
                    if resource in sources:
                        entry = sources[resource]
                        used.add(entry["id"])
                        destination = "upstream-" + Path(entry["path"]).name
                        shutil.copyfile(inputs / entry["path"], directory / destination)
                        replaced.append(destination)
                    else:
                        if "://" in resource: raise ValueError("unavailable offline upstream resource: " + resource)
                        local = inside(directory / resource)
                        if local.is_dir(): prepare(local)
                        elif local.is_file():
                            checksum = digest(local)
                            for identifier, entry in entries.items():
                                if checksum == entry["sha256"]: used.add(identifier)
                        replaced.append(resource)
                if field in config: config[field] = replaced
            configs[0].write_text(yaml.safe_dump(config, sort_keys=False))
        prepare(stage)
        required = ({charts_by_addon[addon][2]} if addon in charts_by_addon else
                    {"calico-vxlan-v3.27.2"} if addon == "calico-vxlan" else
                    {"canal-v3.27.2"} if addon == "cni-canal" else
                    {"vcd-csi-controller.yaml", "vcd-csi-driver.yaml", "vcd-csi-node.yaml"})
        if not required <= used:
            raise ValueError(f"{addon} does not consume its authenticated upstream inputs: {sorted(required-used)}")
        target = output / "rendered" / addon / filename
        target.parent.mkdir(parents=True)
        with target.open("wb") as stream:
            subprocess.run(["kustomize", "build", "--enable-helm", str(stage)], env=environment,
                           stdout=stream, check=True, timeout=180)
        if not target.stat().st_size:
            raise ValueError(f"empty generated manifests for {addon}")
        # Add the runtime templates maintained alongside the generated objects.
        # The generated primary manifest is never copied from the submission.
        for extra in source.iterdir():
            if extra.is_file() and extra.suffix.lower() in {".yaml", ".yml", ".json"} and extra.name != filename and extra.name not in ("kustomization.yaml", "kustomization.yml"):
                shutil.copyfile(extra, target.parent / extra.name)
    (output / "tool-versions.json").write_text(json.dumps(versions, indent=2) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inputs", type=Path, default=Path(__file__).resolve().parent)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("verify")
    importer = commands.add_parser("import")
    importer.add_argument("--id", choices=SOURCES, required=True)
    importer.add_argument("--source", type=Path, required=True)
    importer.add_argument("--sha256", required=True)
    importer.add_argument("--provenance", type=Path, required=True)
    renderer = commands.add_parser("render")
    renderer.add_argument("--addon", action="append", choices=ADDONS)
    renderer.add_argument("--repo", type=Path, required=True)
    renderer.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "import":
        import_input(args.inputs, args.id, args.source, args.sha256, args.provenance)
    elif args.command == "verify":
        verify(args.inputs)
    else:
        render(args.inputs.resolve(), args.repo.resolve(), args.output.resolve(), args.addon)
    print(f"{args.command}: completed")


if __name__ == "__main__":
    main()
