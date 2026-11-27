"""Preserve unsuccessful test trials and recovered interrupted-container text."""
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('export_toolkit', ROOT / 'export-toolkit-results.py')
export = importlib.util.module_from_spec(spec)
spec.loader.exec_module(export)


def main():
    source = ROOT / 'jobs'
    dest = export.OUT / 'reproducibility' / 'excluded-test-records'
    keys = export.local_keys()
    paths = set()
    for job in source.iterdir():
        if not job.is_dir() or not ('test' in job.name or 'baseline' in job.name):
            continue
        for path in job.rglob('result.json'):
            if not (path.parent / 'agent').is_dir():
                continue
            try:
                data = json.loads(path.read_text(encoding='utf-8'))
            except (ValueError, OSError):
                continue
            reward = ((data.get('verifier_result') or {}).get('rewards') or {}).get('reward')
            if data.get('exception_info') or not isinstance(reward, (int, float)):
                paths.update(f for f in path.parent.rglob('*') if f.is_file() and not f.is_symlink())
    interrupted = source / 'interrupted-docker-artifacts'
    if interrupted.is_dir():
        paths.update(f for f in interrupted.rglob('*') if f.is_file() and not f.is_symlink())
    copied = redacted = 0
    excluded = []
    for file in sorted(paths):
        relative = file.relative_to(source)
        try:
            text = file.read_text(encoding='utf-8')
        except (UnicodeError, OSError):
            excluded.append(str(relative))
            continue
        safe = export.redact(text, keys)
        redacted += int(safe != text)
        target = dest / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(safe, encoding='utf-8')
        copied += 1
    manifest = {'copied_text_files': copied, 'redacted_files': redacted,
                'non_text_or_unreadable_files': excluded}
    (export.OUT / 'excluded-test-trace-review.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    print(f'{copied} excluded-test text files; {redacted} redacted; {len(excluded)} omitted')


if __name__ == '__main__':
    main()
