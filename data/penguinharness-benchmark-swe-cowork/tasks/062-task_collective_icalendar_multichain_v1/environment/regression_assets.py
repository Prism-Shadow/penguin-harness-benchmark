"""Verify complete regression assets against the pinned upstream Git object chain."""

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath


# Original author pin was unavailable; retain it as provenance, never as authenticated identity.
SOURCE_REVISION = "f7deda1b1a24e784b7f9a32d026d8dbb9c22b743"
# All 86 production/manifest/document blobs exactly match this public historical commit.
REVISION = "892bc23bae9328d94e14d53578a121bba57914e5"
DEFAULTS = (
    "alarms/example.ics", "calendars/example.ics", "events/rfc_9074_example_3.ics",
    "timezones/pacific_fiji.ics", "todos/example.ics", "availabilities/rfc_7953_1.ics",
)
TEST_ROOT = "src/icalendar/tests/"
SCHEMA = "icalendar-frozen-regression-v2"


def require(condition, message):
    if not condition:
        raise ValueError(message)


def object_id(kind, content):
    return hashlib.sha1(f"{kind} {len(content)}\0".encode() + content).hexdigest()


def tree_entries(content):
    entries = {}
    while content:
        header, remainder = content.split(b"\0", 1)
        mode, name = header.split(b" ", 1)
        require(len(remainder) >= 20, "Truncated Git tree object")
        require(name not in entries and b"/" not in name, "Invalid Git tree entry")
        entries[name] = (mode.decode(), remainder[:20].hex())
        content = remainder[20:]
    return entries


def tests_tree(files):
    directories = {}
    for name, item in files.items():
        if not name.startswith(TEST_ROOT):
            continue
        directory = directories
        parts = PurePosixPath(name[len(TEST_ROOT):]).parts
        for part in parts[:-1]:
            directory = directory.setdefault(part, {})
            require(isinstance(directory, dict), "Conflicting file and directory")
        require(parts[-1] not in directory, "Conflicting regression path")
        directory[parts[-1]] = (item["mode"], item["git_blob"])

    def digest(directory):
        content = bytearray()
        for name, value in sorted(directory.items(), key=lambda entry: (
                entry[0] + ("/" if isinstance(entry[1], dict) else "")).encode()):
            mode, identifier = ("40000", digest(value)) if isinstance(value, dict) else value
            content.extend(f"{mode} {name}\0".encode() + bytes.fromhex(identifier))
        return object_id("tree", content)

    return digest(directories)


def verify_record(record, contents, revision=REVISION):
    require(record.get("schema") == SCHEMA, "Missing authenticated v2 manifest; rerun the frozen Git importer")
    require(record["upstream_revision"] == revision, "Wrong frozen upstream revision")
    proof = record["git_proof"]
    commit = bytes.fromhex(proof["commit"])
    require(object_id("commit", commit) == revision, "Commit proof does not match pinned revision")
    root_line = commit.split(b"\n", 1)[0]
    require(root_line.startswith(b"tree "), "Commit proof has no root tree")
    tree_id = root_line[5:].decode()
    root_entries = None
    for directory, child in (("", b"src"), ("src", b"icalendar"), ("src/icalendar", b"tests")):
        content = bytes.fromhex(proof["trees"][directory])
        require(object_id("tree", content) == tree_id, f"Tree proof mismatch: {directory or '/'}")
        entries = tree_entries(content)
        if root_entries is None:
            root_entries = entries
        require(child in entries and entries[child][0] == "40000", f"Missing upstream subtree: {child!r}")
        tree_id = entries[child][1]
    files = record["files"]
    require(set(contents) == set(files), "Incomplete regression content set")
    for name, item in files.items():
        relative = PurePosixPath(name)
        require(name == "conftest.py" or name.startswith(TEST_ROOT), f"Non-regression asset: {name}")
        require(not relative.is_absolute() and ".." not in relative.parts
                and relative.as_posix() == name and "\\" not in name, f"Unsafe path: {name}")
        require(not any(part in {"__pycache__", ".pytest_cache", ".mypy_cache", ".hypothesis"}
                        for part in relative.parts) and not name.endswith((".pyc", ".pyo")), f"Cache asset: {name}")
        require(item["mode"] in {"100644", "100755"}, f"Unsafe mode: {name}")
        content = contents[name]
        require(hashlib.sha256(content).hexdigest() == item["sha256"], f"SHA256 mismatch: {name}")
        require(object_id("blob", content) == item["git_blob"], f"Git blob mismatch: {name}")
    require(tests_tree(files) == tree_id == record["upstream_tree"], "Incomplete or modified upstream tests tree")
    conftest = root_entries.get(b"conftest.py")
    expected = files.get("conftest.py")
    require(conftest == ((expected["mode"], expected["git_blob"]) if expected else None),
            "Missing or modified frozen root conftest.py")
    require(any(PurePosixPath(name).name.startswith("test_") and name.endswith(".py")
                for name in files), "Missing upstream tests")
    for name in DEFAULTS:
        require(TEST_ROOT + name in files, f"Missing default example: {name}")
    require(sum(map(len, contents.values())) < 32 * 1024 * 1024, "Regression assets exceed size limit")


def verify_directory(public_repo, revision=REVISION):
    manifest = public_repo / "UPSTREAM_REGRESSION.json"
    require(manifest.is_file(), "Blocked: missing authenticated frozen upstream tests/example assets; smoke tests are not full regression")
    require(not any(path.is_symlink() for path in (manifest, *manifest.parents)), "Symlinked manifest")
    record = json.loads(manifest.read_text())
    contents = {}
    for name in record["files"]:
        relative = PurePosixPath(name)
        require(not relative.is_absolute() and ".." not in relative.parts
                and (name == "conftest.py" or name.startswith(TEST_ROOT)), f"Unsafe asset: {name}")
        path = public_repo / name
        require(not any(parent.is_symlink() for parent in (path, *path.parents)), f"Symlinked asset: {name}")
        contents[name] = path.read_bytes()
        mode = "100755" if path.stat().st_mode & 0o111 else "100644"
        require(mode == record["files"][name]["mode"], f"Changed executable mode: {name}")
    verify_record(record, contents, revision)
    return hashlib.sha256(manifest.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--public-repo", required=True, type=Path)
    arguments = parser.parse_args()
    try:
        checksum = verify_directory(arguments.public_repo)
    except (ValueError, KeyError, OSError) as error:
        parser.exit(1, f"REGRESSION_ASSETS_BLOCKED: {error}\n")
    print(f"Authenticated complete frozen regression assets: {checksum}")
    print("Behavioral compatibility remains pending full baseline/gold pytest and default example() execution.")


if __name__ == "__main__":
    main()
