"""Expose toolkit bookkeeping to the continuing Codex training session."""
import argparse
import json
from pathlib import Path

from algorithms import diff_hunks, openskill_final, skilladam_step, skillopt_budget, strict_improvement, trace_select


def files(path: str) -> dict[str, bytes]:
    root = Path(path)
    return {str(p.relative_to(root)): p.read_bytes() for p in root.rglob('*') if p.is_file()}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('method', choices=('skilladam', 'skillopt', 'trace', 'openskill'))
    parser.add_argument('request', type=Path)
    args = parser.parse_args()
    data = json.loads(args.request.read_text(encoding='utf-8'))
    if args.method == 'skilladam':
        result = skilladam_step(data['current'], data['candidate'], data['previous_variance'],
                                data.get('beta2', 0.9), data.get('base_budget', 4),
                                data.get('min_budget', 1), data.get('variance_cap', 0.1))
        if 'old_skill' in data and 'candidate_skill' in data:
            hunks = diff_hunks(Path(data['old_skill']).read_text(encoding='utf-8'),
                               Path(data['candidate_skill']).read_text(encoding='utf-8'))
            result['hunks'] = hunks
            result['within_budget'] = hunks <= data['edit_budget']
            if not result['within_budget']:
                result.update(accepted=False, variance=data['previous_variance'],
                              next_budget=data['edit_budget'])
    elif args.method == 'skillopt':
        result = {'budget': skillopt_budget(data['step'], data['total_steps'])}
        if 'edits' in data:
            result['within_budget'] = len(data['edits']) <= result['budget']
        if 'current' in data and 'candidate' in data:
            result['accepted'] = strict_improvement(data['current'], data['candidate'])
            if not result.get('within_budget', True):
                result['accepted'] = False
    elif args.method == 'trace':
        stages = [dict(stage, bank=files(stage['bank_path'])) for stage in data['stages']]
        result = trace_select(stages, data['tasks'], data['attempts'])
    else:
        result = openskill_final(data['revisions'])
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()
