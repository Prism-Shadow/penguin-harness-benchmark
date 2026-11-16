"""Prepare redacted text records from toolkit training jobs for review."""
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('export_toolkit', ROOT / 'export-toolkit-results.py')
export = importlib.util.module_from_spec(spec)
spec.loader.exec_module(export)


def main():
    source = ROOT / 'jobs'
    dest = export.OUT / 'reproducibility' / 'training-jobs'
    selected = [p for p in source.iterdir() if p.is_dir() and
                (p.name.endswith('-train') or p.name.startswith('interrupted-engineering-skillopt-'))]
    keys = export.local_keys()
    copied = redacted = 0
    skipped = []
    for job in sorted(selected):
        for file in job.rglob('*'):
            if not file.is_file() or file.is_symlink():
                continue
            relative = file.relative_to(source)
            try:
                text = file.read_text(encoding='utf-8')
            except (UnicodeDecodeError, OSError):
                skipped.append(str(relative))
                continue
            safe = export.redact(text, keys)
            redacted += int(safe != text)
            target = dest / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(safe, encoding='utf-8')
            copied += 1
    manifest = {'jobs': [p.name for p in sorted(selected)], 'copied_text_files': copied,
                'redacted_files': redacted, 'non_text_or_unreadable_files': skipped}
    (export.OUT / 'training-trace-review.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    print(f'{len(selected)} training job directories; {copied} text files; {redacted} redacted; {len(skipped)} excluded')


if __name__ == '__main__':
    main()
