#!/usr/bin/env python3
"""Display the absolute soft deadline written by Penguin's run supervisor."""
import argparse
import json
import math
import time
from pathlib import Path


def remaining_seconds(path: Path, now_ms: int | None = None) -> int:
    state = json.loads(path.read_text())
    deadline = state['deadline_ms']
    if type(deadline) is not int or deadline <= 0:
        raise ValueError('Invalid deadline timestamp')
    return max(0, math.ceil((deadline - (int(time.time() * 1000) if now_ms is None else now_ms)) / 1000))


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--deadline', type=Path, default=Path('/tmp/ptb-penguin-deadline.json'))
    args = ap.parse_args()
    try:
        seconds = remaining_seconds(args.deadline)
    except (OSError, ValueError, KeyError) as exc:
        ap.exit(1, f'Timer not initialized by the agent runner: {exc}\n')
    print(f'Remaining time (hours:minutes:seconds): {seconds // 3600}:{seconds % 3600 // 60:02d}:{seconds % 60:02d}' if seconds else 'Timer expired!')
