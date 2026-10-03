#!/usr/bin/env python3
"""List-price spend so far of the trials in some Harbor jobs, as one JSON line.

    python3 tools/measure/spend.py <jobs dir> <job glob>...

A finished trial counts its result.json `agent_result.cost_usd`. A trial still verifying has
no result.json yet, but the adapter has already written agent/penguin-cost-by-session.json
(the same `penguin cost` numbers), which counts instead; so does a finished trial whose
cost_usd is null (`cost_from_logs`). A trial still in its agent phase has no cost yet
(`in_agent_phase`): guard.sh reserves an amount for each. Standard library only.

    {"cost_usd": 4.2, "finished": 30, "errors": 1, "verifying": 2, "in_agent_phase": 5, "cost_from_logs": 0}
"""

from __future__ import annotations

import glob
import json
import os
import sys


def _load(path: str):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def _session_cost(path: str) -> float:
    groups = (_load(path) or {}).get("groups") or []
    return sum(g.get("cost") or 0 for g in groups if isinstance(g, dict))


def main() -> int:
    if len(sys.argv) < 3:
        print(__doc__, file=sys.stderr)
        return 2
    jobs_dir, patterns = sys.argv[1], sys.argv[2:]
    total, finished, verifying, in_agent, from_logs, errors = 0.0, 0, 0, 0, 0, 0
    seen: set[str] = set()
    for pattern in patterns:
        for job in sorted(glob.glob(os.path.join(jobs_dir, pattern))):
            if job in seen or not os.path.isdir(job):
                continue
            seen.add(job)
            for trial in sorted(glob.glob(os.path.join(job, "*__*"))):
                if not os.path.isdir(trial):
                    continue
                result_path = os.path.join(trial, "result.json")
                cost_path = os.path.join(trial, "agent", "penguin-cost-by-session.json")
                if os.path.exists(result_path):
                    result = _load(result_path)
                    if not isinstance(result, dict):
                        continue  # being written
                    finished += 1
                    if result.get("exception_info"):
                        errors += 1
                    cost = (result.get("agent_result") or {}).get("cost_usd")
                    if isinstance(cost, (int, float)):
                        total += cost
                    elif os.path.exists(cost_path):
                        total += _session_cost(cost_path)
                        from_logs += 1
                elif os.path.exists(cost_path):
                    verifying += 1
                    total += _session_cost(cost_path)
                else:
                    in_agent += 1
    print(json.dumps({"cost_usd": round(total, 4), "finished": finished, "errors": errors,
                      "verifying": verifying, "in_agent_phase": in_agent, "cost_from_logs": from_logs}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
