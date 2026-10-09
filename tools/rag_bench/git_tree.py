#!/usr/bin/env python3
"""Print (or check) the git tree id of a directory's content.

`fetch.sh` downloads rag-bench-essential as a GitHub archive tarball, which
carries no checksum of its own. Hashing the extracted files the way git does
(blobs, then trees with their modes) and comparing the result with the pinned
commit's tree id proves the download is byte-for-byte that commit. Standard
library only, so it runs wherever `python3` does.

    python3 tools/rag_bench/git_tree.py <dir>            # print the tree id
    python3 tools/rag_bench/git_tree.py <dir> <tree id>  # exit 1 unless equal

Matches `git archive` output for trees without export-ignore/export-subst
attributes or submodules (rag-bench-essential has none). Empty directories are
skipped, as git does not track them.
"""

from __future__ import annotations

import hashlib
import os
import stat
import sys


def _object_id(kind: bytes, data: bytes) -> bytes:
    return hashlib.sha1(kind + b" " + str(len(data)).encode() + b"\0" + data).digest()


def tree_id(path: str) -> bytes | None:
    """Raw 20-byte tree id of `path`, or None for a directory with no files."""
    entries = []
    for name in os.listdir(path):
        full = os.path.join(path, name)
        st = os.lstat(full)
        if stat.S_ISLNK(st.st_mode):
            mode, oid = b"120000", _object_id(b"blob", os.fsencode(os.readlink(full)))
        elif stat.S_ISDIR(st.st_mode):
            oid = tree_id(full)
            if oid is None:
                continue
            mode = b"40000"
        elif stat.S_ISREG(st.st_mode):
            mode = b"100755" if st.st_mode & stat.S_IXUSR else b"100644"
            with open(full, "rb") as f:
                oid = _object_id(b"blob", f.read())
        else:
            raise ValueError(f"unsupported file type: {full}")
        raw_name = os.fsencode(name)
        # git orders tree entries by name, with directories compared as "name/".
        sort_key = raw_name + (b"/" if mode == b"40000" else b"")
        entries.append((sort_key, mode + b" " + raw_name + b"\0" + oid))
    if not entries:
        return None
    entries.sort()
    return _object_id(b"tree", b"".join(entry for _, entry in entries))


def main() -> int:
    if len(sys.argv) not in (2, 3):
        print(__doc__, file=sys.stderr)
        return 2
    oid = tree_id(sys.argv[1])
    actual = oid.hex() if oid else ""
    if len(sys.argv) == 2:
        print(actual)
        return 0
    expected = sys.argv[2].strip().lower()
    if actual != expected:
        print(f"tree mismatch for {sys.argv[1]}: got {actual}, expected {expected}", file=sys.stderr)
        return 1
    print(f"tree {actual} verified")
    return 0


if __name__ == "__main__":
    sys.exit(main())
