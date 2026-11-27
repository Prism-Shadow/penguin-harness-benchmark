"""Count optimizer and delegated Codex usage from a completed training trial."""
import argparse
import json
from pathlib import Path


def summarize(trial: Path) -> dict:
    result = json.loads((trial / 'result.json').read_text(encoding='utf-8'))
    outer = result.get('agent_result') or {}
    keys = {'input_tokens': 'n_input_tokens', 'cached_input_tokens': 'n_cache_tokens',
            'output_tokens': 'n_output_tokens'}
    if any(outer.get(name) is None for name in keys.values()):
        raise ValueError('optimizer usage is incomplete')
    total = {name: outer[source] for name, source in keys.items()}
    records = trial / 'artifacts/submission/records'
    if not records.is_dir():
        raise ValueError('training delegation records are missing')
    actor_ids = set()
    calls = 0
    for transcript in records.rglob('events.jsonl'):
        record_path = transcript.parent / 'result.json'
        if not record_path.is_file():
            raise ValueError(f'delegated result is missing: {transcript}')
        item = json.loads(record_path.read_text(encoding='utf-8'))
        if not item.get('complete') or item.get('restricted_command_detected'):
            raise ValueError(f'incomplete or restricted delegated session: {transcript}')
        if item['role'] == 'actor':
            if item['session_id'] in actor_ids:
                raise ValueError('actor session was reused')
            actor_ids.add(item['session_id'])
        for usage in item['usage']:
            for key in total:
                if usage.get(key) is None:
                    raise ValueError(f'incomplete delegated usage: {transcript}')
                total[key] += usage[key]
        calls += 1
    if not calls:
        raise ValueError('training contains no delegated session records')
    return {'total': total, 'delegated_calls': calls, 'actor_sessions': len(actor_ids)}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('trial', type=Path)
    args = parser.parse_args()
    print(json.dumps(summarize(args.trial), indent=2))
