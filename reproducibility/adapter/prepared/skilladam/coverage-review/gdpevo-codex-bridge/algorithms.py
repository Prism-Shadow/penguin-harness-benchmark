"""Deterministic bookkeeping used by the four RSI toolkit adaptations."""
from __future__ import annotations

import math
import difflib
import statistics
from collections import defaultdict


def strict_improvement(current: list[float], candidate: list[float]) -> bool:
    if not current or len(current) != len(candidate):
        raise ValueError('current and candidate must cover the same nonempty task set')
    for score in (*current, *candidate):
        if not isinstance(score, (int, float)) or not math.isfinite(score) or not 0 <= score <= 1:
            raise ValueError('scores must be finite normalized values')
    return statistics.mean(candidate) > statistics.mean(current)


def skilladam_step(current: list[float], candidate: list[float], previous_variance: float,
                   beta2: float = 0.9, base_budget: int = 4,
                   min_budget: int = 1, variance_cap: float = 0.1) -> dict:
    accepted = strict_improvement(current, candidate)
    if not 0 <= beta2 <= 1 or variance_cap <= 0 or not 0 <= previous_variance:
        raise ValueError('invalid adaptive-budget parameters')
    deltas = [b - a for a, b in zip(current, candidate)]
    batch_variance = statistics.variance(deltas) if len(deltas) > 1 else 0.0
    variance = beta2 * previous_variance + (1 - beta2) * batch_variance
    clipped = min(1.0, max(0.0, variance / variance_cap))
    budget = max(min_budget, round(base_budget * (1 - clipped)))
    return {'accepted': accepted, 'batch_variance': batch_variance,
            'variance': variance, 'next_budget': budget}


def skillopt_budget(step: int, total_steps: int, maximum: int = 4, minimum: int = 2) -> int:
    if total_steps < 1 or not 1 <= step <= total_steps or minimum > maximum:
        raise ValueError('invalid SkillOpt schedule')
    if total_steps == 1:
        return maximum
    return max(minimum, round(minimum + (maximum - minimum) *
                              (1 + math.cos(math.pi * step / total_steps)) / 2))


def diff_hunks(before: str, after: str) -> int:
    return sum(line.startswith('@@ ') for line in difflib.unified_diff(
        before.splitlines(keepends=True), after.splitlines(keepends=True)))


def trace_select(stages: list[dict], expected_tasks: list[str], attempts: int) -> dict:
    """Choose the best complete bank; pool measurements from byte-identical banks."""
    if not stages or not expected_tasks or attempts < 1:
        raise ValueError('TRACE needs candidate stages and complete batches')
    grouped: list[dict] = []
    for stage in stages:
        by_task = defaultdict(list)
        for record in stage['records']:
            if record['task'] not in expected_tasks:
                raise ValueError('unexpected task in TRACE batch')
            score = record['score']
            if not isinstance(score, (int, float)) or not math.isfinite(score) or not 0 <= score <= 1:
                raise ValueError('invalid TRACE score')
            by_task[record['task']].append(score)
        if any(len(by_task[t]) != attempts for t in expected_tasks):
            raise ValueError('incomplete TRACE batch')
        existing = next((x for x in grouped if x['bank'] == stage['bank']), None)
        if existing is None:
            existing = {'stage': stage['stage'], 'bank': stage['bank'], 'by_task': defaultdict(list)}
            grouped.append(existing)
        for task in expected_tasks:
            existing['by_task'][task].extend(by_task[task])
    for item in grouped:
        item['mean'] = statistics.mean(statistics.mean(item['by_task'][t]) for t in expected_tasks)
    winner = max(grouped, key=lambda item: item['mean'])
    return {'stage': winner['stage'], 'mean': winner['mean']}


def openskill_final(revisions: list[dict]) -> dict:
    """OpenSkill exports the last valid revision, not the best virtual score."""
    valid = [item for item in revisions if item.get('valid')]
    if not valid:
        raise ValueError('no valid OpenSkill revision')
    return valid[-1]
