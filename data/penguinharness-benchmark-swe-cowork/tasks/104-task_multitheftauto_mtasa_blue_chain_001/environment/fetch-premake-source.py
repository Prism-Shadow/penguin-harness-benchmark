#!/usr/bin/env python3
import argparse
import hashlib
import http.client
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import ssl
import stat
import sys
import tempfile
import time
import urllib.error
import urllib.request
import zipfile


LOCK = json.loads(Path(__file__).with_name("premake-source.lock.json").read_text())
TAG = LOCK["source_tag"]
ASSET_NAME = "premake-5.0.0-beta7-src.zip"
RELEASE_URL = "https://api.github.com/repos/premake/premake-core/releases/tags/" + TAG
ASSET_URL = "https://github.com/premake/premake-core/releases/download/" + TAG + "/" + ASSET_NAME
MAX_ARCHIVE_BYTES = 64 * 1024 * 1024
MAX_EXPANDED_BYTES = 128 * 1024 * 1024


def download(url, destination, limit, attempts=4, expected_size=None):
    accept = "application/vnd.github+json" if url == RELEASE_URL else "application/octet-stream"
    request = urllib.request.Request(url, headers={"User-Agent": "mta-task-toolchain-builder", "Accept": accept})
    for attempt in range(attempts):
        try:
            with urllib.request.urlopen(request, timeout=60) as response, destination.open("wb") as output:
                total = 0
                while True:
                    block = response.read(64 * 1024)
                    if not block:
                        break
                    total += len(block)
                    if total > limit:
                        raise ValueError("download exceeds size limit")
                    output.write(block)
            if expected_size is not None and total != expected_size:
                raise http.client.IncompleteRead(b"", expected_size - total)
            return
        except (urllib.error.URLError, TimeoutError, ConnectionError, ssl.SSLError, http.client.HTTPException) as error:
            destination.unlink(missing_ok=True)
            if isinstance(error, urllib.error.HTTPError) and error.code not in (408, 429, 500, 502, 503, 504):
                raise
            if attempt + 1 == attempts:
                raise
            print(f"source download attempt {attempt + 1}/{attempts} failed: {error}; retrying", file=sys.stderr, flush=True)
            time.sleep(2 ** attempt)


def select_asset(release):
    if release.get("tag_name") != TAG or release.get("draft") is not False:
        raise ValueError("unexpected Premake release")
    assets = [asset for asset in release["assets"] if asset.get("name") == ASSET_NAME]
    if len(assets) != 1:
        raise ValueError("expected exactly one official source ZIP asset")
    asset = assets[0]
    if asset.get("browser_download_url") != ASSET_URL:
        raise ValueError("unexpected source download URL")
    if not isinstance(asset.get("size"), int) or not 0 < asset["size"] <= MAX_ARCHIVE_BYTES:
        raise ValueError("invalid source archive size")
    digest = asset.get("digest") or ""
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", digest):
        raise ValueError("GitHub release lacks a published SHA256; require independent source verification")
    return asset


def unpack(archive, destination):
    with zipfile.ZipFile(archive) as source:
        members = source.infolist()
        if sum(member.file_size for member in members) > MAX_EXPANDED_BYTES:
            raise ValueError("source archive expands beyond size limit")
        seen = set()
        for member in members:
            path = PurePosixPath(member.filename)
            mode = member.external_attr >> 16
            if path.is_absolute() or not path.parts or ".." in path.parts or "\\" in member.filename or ":" in member.filename:
                raise ValueError("unsafe source archive path")
            if stat.S_IFMT(mode) not in (0, stat.S_IFREG, stat.S_IFDIR):
                raise ValueError("source archive contains a link or special file")
            if str(path) in seen:
                raise ValueError("duplicate source archive path")
            seen.add(str(path))
        for member in members:
            target = destination / member.filename
            if member.is_dir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                with source.open(member) as input_file, target.open("wb") as output:
                    shutil.copyfileobj(input_file, output, 64 * 1024)
                target.chmod(0o644 | ((member.external_attr >> 16) & 0o111))
    if (destination / "Bootstrap.mak").is_file():
        return destination
    children = list(destination.iterdir())
    if len(children) == 1 and children[0].is_dir() and (children[0] / "Bootstrap.mak").is_file():
        return children[0]
    raise ValueError("source release does not contain Bootstrap.mak at its root")


def acquire(destination, expected_sha256=None):
    if destination.exists() or destination.is_symlink():
        raise ValueError("source destination must not exist")
    if expected_sha256 is not None and not re.fullmatch(r"[0-9a-f]{64}", expected_sha256):
        raise ValueError("invalid independently pinned source SHA256")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="premake-download-", dir=destination.parent) as temporary:
        temporary = Path(temporary)
        metadata = temporary / "release.json"
        download(RELEASE_URL, metadata, 1024 * 1024)
        release = json.loads(metadata.read_text())
        asset = select_asset(release)
        published_sha256 = asset["digest"].split(":", 1)[1]
        if expected_sha256 is not None and published_sha256 != expected_sha256:
            raise ValueError("published source digest does not match independent pin")
        archive = temporary / ASSET_NAME
        download(ASSET_URL, archive, asset["size"], expected_size=asset["size"])
        digest = hashlib.sha256(archive.read_bytes()).hexdigest()
        if archive.stat().st_size != asset["size"] or digest != published_sha256:
            raise ValueError("source archive size or SHA256 mismatch")
        extracted = temporary / "extracted"
        extracted.mkdir()
        root = unpack(archive, extracted)
        record = {
            "source_url": ASSET_URL,
            "source_tag": TAG,
            "release_id": release["id"],
            "asset_id": asset["id"],
            "archive_sha256": digest,
            "published_sha256": published_sha256,
            "independently_pinned": expected_sha256 is not None,
        }
        (root / ".source-provenance.json").write_text(json.dumps(record, indent=2) + "\n")
        os.replace(root, destination)
        print(json.dumps(record, sort_keys=True), flush=True)


def main():
    parser = argparse.ArgumentParser(description="Fetch the official Premake source release, with bounded retries and digest verification.")
    parser.add_argument("destination", type=Path)
    parser.add_argument("--sha256", default=os.environ.get("PREMAKE_SOURCE_SHA256") or LOCK["archive_sha256"])
    arguments = parser.parse_args()
    acquire(arguments.destination, arguments.sha256)


if __name__ == "__main__":
    main()
