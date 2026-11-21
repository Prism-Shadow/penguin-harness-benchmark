#!/usr/bin/env python3
"""Redact PTB-specific credentials that are not part of Penguin's model configuration."""
import json
import os
from pathlib import Path
import sys


def redact(paths, secrets):
    values = set()
    for secret in secrets:
        if secret:
            values.add(secret)
            values.add(json.dumps(secret)[1:-1])
    changed = 0
    for root in paths:
        files = [root] if root.is_file() else (p for p in root.rglob('*') if p.is_file() and not p.is_symlink())
        for path in files:
            try:
                text = path.read_text(encoding='utf-8')
            except (UnicodeError, OSError):
                continue
            new = text
            for value in sorted(values, key=len, reverse=True):
                new = new.replace(value, '[REDACTED]')
            if new != text:
                path.write_text(new, encoding='utf-8')
                changed += 1
    return changed


if __name__ == '__main__':
    redact([Path(p) for p in sys.argv[1:]], [os.environ.get(k, '') for k in ('HF_TOKEN', 'OPENAI_API_KEY', 'CODEX_API_KEY')])
