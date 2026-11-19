#!/usr/bin/env python3
"""Reject cached TelegramBots artifacts; reactor source is the only implementation."""
import argparse
import io
from pathlib import Path
import tarfile
import zipfile


MAX_DEPTH = 4
MAX_NESTED_BYTES = 64 * 1024 * 1024
MAX_MEMBERS = 50000
ARCHIVE_SUFFIXES = (".jar", ".whl", ".zip", ".tar", ".tar.gz", ".tgz")


def target_path(name):
    normalized = "/" + name.replace("\\", "/").strip("/") + "/"
    return "/org/telegram/" in normalized or "/org.telegram/" in normalized


def target_metadata(name, data):
    if name.endswith((".pom", "pom.xml")):
        return b"org.telegram" in data and b"telegrambots" in data.lower()
    if name.endswith(".java"):
        return b"package org.telegram." in data
    return False


def inspect_archive(stream, label, depth, budget):
    if depth > MAX_DEPTH:
        raise ValueError("nested archive depth exceeds audit limit")
    if zipfile.is_zipfile(stream):
        with zipfile.ZipFile(stream) as contents:
            members = [(member.filename, member.file_size, member) for member in contents.infolist()]
            return inspect_members(members, contents.open, label, depth, budget)
    if hasattr(stream, "seek"):
        stream.seek(0)
    with tarfile.open(fileobj=stream if hasattr(stream, "read") else None,
                      name=None if hasattr(stream, "read") else str(stream), mode="r:*") as contents:
        members = []
        for member in contents:
            if member.issym() or member.islnk():
                if target_path(member.name) or target_path(member.linkname):
                    return True
            if member.isfile():
                members.append((member.name, member.size, member))
            if len(members) > MAX_MEMBERS:
                raise ValueError("archive member count exceeds audit limit")
        return inspect_members(members, contents.extractfile, label, depth, budget)


def inspect_members(members, open_member, label, depth, budget):
    budget[1] -= len(members)
    if budget[1] < 0:
        raise ValueError("archive member count exceeds audit limit")
    for name, size, member in members:
        if target_path(name):
            return True
        nested = name.lower().endswith(ARCHIVE_SUFFIXES)
        metadata = name.endswith((".pom", "pom.xml", ".java"))
        if not (nested or metadata):
            continue
        if size > budget[0]:
            raise ValueError("nested archive bytes exceed audit limit")
        budget[0] -= size
        with open_member(member) as content:
            data = content.read(size + 1)
        if len(data) != size:
            raise ValueError("archive member size mismatch")
        if target_metadata(name, data):
            return True
        if nested and inspect_archive(io.BytesIO(data), label + "!" + name, depth + 1, budget):
            return True
    return False


def audit(roots):
    problems = []
    scanned = 0
    for root in roots:
        if root.is_symlink():
            problems.append(str(root) + " (cache root symlink requires isolated audit)")
            continue
        if not root.exists():
            continue
        for archive in sorted(root.rglob("*")):
            if archive.is_symlink():
                try:
                    destination = archive.resolve(strict=True)
                    if target_path(str(archive)) or not destination.is_relative_to(root.resolve()):
                        problems.append(str(archive) + " (dependency symlink requires isolated audit)")
                except (OSError, RuntimeError) as error:
                    problems.append(str(archive) + " (symlink audit failed: " + str(error) + ")")
                continue
            if not archive.is_file():
                continue
            try:
                if target_path(str(archive)):
                    problems.append(str(archive))
                    continue
                if archive.name.endswith((".pom", "pom.xml", ".java")):
                    if archive.stat().st_size > MAX_NESTED_BYTES:
                        raise ValueError("metadata exceeds audit limit")
                    if target_metadata(archive.name, archive.read_bytes()):
                        problems.append(str(archive))
                        continue
                if archive.name.lower().endswith(ARCHIVE_SUFFIXES) or zipfile.is_zipfile(archive):
                    scanned += 1
                    if inspect_archive(archive, str(archive), 0, [MAX_NESTED_BYTES, MAX_MEMBERS]):
                        problems.append(str(archive))
            except (OSError, ValueError, RuntimeError, zipfile.BadZipFile, tarfile.TarError) as error:
                problems.append(str(archive) + " (audit failed: " + str(error) + ")")
    return scanned, problems


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("roots", nargs="+", type=Path)
    args = parser.parse_args()
    scanned, problems = audit(args.roots)
    print(f"dependency archives scanned={scanned}; prohibited or unaudited entries={len(problems)}")
    for problem in problems:
        print(problem)
    return int(bool(problems))


if __name__ == "__main__":
    raise SystemExit(main())
