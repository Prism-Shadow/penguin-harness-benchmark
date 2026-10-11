#!/usr/bin/env python3
"""Where the time of a GDPevo protocol replica went, step by step.

    python3 tools/gdpevo/protocol/timeline.py <out dir> [<out dir>...] [--root <data root>] [--json <file>]

Each <out dir> is a replica's output directory (replica.sh's --out, jobs/protocol-<id>) or its
state/ directory; the data root is the one its state/meta.json names, or --root when a single
replica is given (for a root copied elsewhere). For every step that has a state/<step>.meta.json,
the step's window is that record's start and finish, and its trials are those of the step's
Benchmark under <data root>/default_project/benchmarks/<benchmark>/.jobs/ that started inside the
window (a trial directory without result.json counts as unfinished, dated by its config.json).
It prints per step:

- the trials: finished, unfinished, how the CLI was installed (`agent_result.metadata.install`:
  bundle or network) and how many failed for want of a Docker network (`exception_info` names
  an exhausted address pool);
- the phase medians, in seconds, of Harbor's environment_setup, agent_setup, agent_execution and
  verifier stamps;
- the minutes during which exactly k trials were running, and the effective concurrency: the sum
  of the trials' durations over the step's wall time;
- from state/<step>.log.json, the controller's own messages (`penguin session log` inlines the
  subagents' as well; the controller's are the ones with a trace position): its run_subagent and
  input_subagent calls, the subagent completion notices it received (`[background_task_done]`,
  kind subagent), and the time from each notice to its next run_subagent call — notices after the
  last launch have none.

--json writes the same numbers to a file. Standard library only.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import statistics
import sys

STEPS = ["B0", "T0", "O1", "T1"]
PHASES = ["environment_setup", "agent_setup", "agent_execution", "verifier"]
POOL_ERROR = re.compile(r"non-overlapping IPv4 address pool|address pools have been fully subnetted", re.I)
SUBAGENT_NOTICE = re.compile(r"^kind:\s*subagent\s*$", re.M)


def load_json(path: str, default=None):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def parse_time(text) -> dt.datetime | None:
    if not isinstance(text, str) or not text:
        return None
    try:
        value = dt.datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    return value if value.tzinfo else value.replace(tzinfo=dt.timezone.utc)


def span(stamps) -> float | None:
    if not isinstance(stamps, dict):
        return None
    start, end = parse_time(stamps.get("started_at")), parse_time(stamps.get("finished_at"))
    return (end - start).total_seconds() if start and end else None


def median(values: list[float]) -> float | None:
    return round(statistics.median(values), 1) if values else None


def read_trials(jobs_dir: str) -> list[dict]:
    """Every trial directory two levels under .jobs/ (<job>/<trial>), read with os.listdir: the
    directory is hidden, which recursive globbing skips."""
    trials = []
    for job in sorted(os.listdir(jobs_dir)) if os.path.isdir(jobs_dir) else []:
        job_dir = os.path.join(jobs_dir, job)
        if not os.path.isdir(job_dir):
            continue
        for name in sorted(os.listdir(job_dir)):
            trial_dir = os.path.join(job_dir, name)
            if not os.path.isdir(trial_dir) or "__" not in name:
                continue
            result = load_json(os.path.join(trial_dir, "result.json"))
            if not isinstance(result, dict):
                try:
                    mtime = os.path.getmtime(os.path.join(trial_dir, "config.json"))
                except OSError:
                    mtime = os.path.getmtime(trial_dir)
                trials.append({"trial": name, "finished": False,
                               "started": dt.datetime.fromtimestamp(mtime, dt.timezone.utc)})
                continue
            exception = result.get("exception_info")
            metadata = (result.get("agent_result") or {}).get("metadata") or {}
            trials.append({
                "trial": name,
                "finished": True,
                "started": parse_time(result.get("started_at")),
                "ended": parse_time(result.get("finished_at")),
                "phases": {phase: span(result.get(phase)) for phase in PHASES},
                "install": metadata.get("install") or "unknown",
                "pool_error": bool(exception) and bool(POOL_ERROR.search(json.dumps(exception))),
            })
    return trials


def running_minutes(trials: list[dict], start: dt.datetime, end: dt.datetime) -> dict[int, float]:
    """k -> minutes of the window during which exactly k of the trials were running."""
    events = []
    for t in trials:
        s, e = max(t["started"], start), min(t["ended"], end)
        if s < e:
            events += [(s, 1), (e, -1)]
    events.sort(key=lambda event: (event[0], event[1]))
    minutes: dict[int, float] = {}
    k, previous = 0, start
    for when, delta in events:
        minutes[k] = minutes.get(k, 0.0) + (when - previous).total_seconds() / 60
        k, previous = k + delta, when
    minutes[k] = minutes.get(k, 0.0) + max((end - previous).total_seconds(), 0) / 60
    return {k: round(v, 1) for k, v in sorted(minutes.items()) if v >= 0.05}


def controller_activity(log_path: str) -> dict | None:
    messages = load_json(log_path)
    if not isinstance(messages, list):
        return None
    own = [m for m in messages if isinstance(m, dict) and m.get("tracePosition") is not None]
    controller_only = bool(own)
    launches, notices, waits = [], [], 0
    for m in own if controller_only else [m for m in messages if isinstance(m, dict)]:
        payload = m.get("payload")
        when = parse_time(m.get("timestamp"))
        if m.get("type") != "model_msg" or not isinstance(payload, dict) or when is None:
            continue
        if payload.get("type") == "tool_call" and payload.get("name") == "run_subagent":
            launches.append(when)
        elif payload.get("type") == "tool_call" and payload.get("name") == "input_subagent":
            waits += 1
        elif payload.get("type") == "text" and payload.get("role") == "user":
            text = str(payload.get("text") or "")
            if text.startswith("[background_task_done]") and SUBAGENT_NOTICE.search(text):
                notices.append(when)
    launches.sort()
    latencies = []
    for notice in sorted(notices):
        following = next((launch for launch in launches if launch >= notice), None)
        if following is not None:
            latencies.append((following - notice).total_seconds())
    return {
        "controller_only": controller_only,
        "run_subagent": len(launches),
        "input_subagent": waits,
        "subagent_notices": len(notices),
        "notices_followed_by_a_launch": len(latencies),
        "notice_to_launch_median_s": median(latencies),
        "notice_to_launch_max_s": round(max(latencies), 1) if latencies else None,
        "first_launch": launches[0].isoformat() if launches else None,
    }


def step_timeline(state: str, root: str, name: str, trials_by_bench: dict[str, list[dict]]) -> dict | None:
    meta = load_json(os.path.join(state, f"{name}.meta.json"))
    if not isinstance(meta, dict):
        return None
    start = parse_time(meta.get("started"))
    end = parse_time(meta.get("finished")) or dt.datetime.now(dt.timezone.utc)
    bench = meta.get("benchmark") or ""
    if bench not in trials_by_bench:
        trials_by_bench[bench] = read_trials(os.path.join(root, "default_project", "benchmarks", bench, ".jobs"))
    inside = [t for t in trials_by_bench[bench] if start and t["started"] and start <= t["started"] <= end]
    done = [t for t in inside if t["finished"] and t["started"] and t["ended"]]
    wall = (end - start).total_seconds() if start else None
    installs: dict[str, int] = {}
    for t in done:
        installs[t["install"]] = installs.get(t["install"], 0) + 1
    controller = controller_activity(os.path.join(state, f"{name}.log.json"))
    if controller and controller["first_launch"] and start:
        controller["first_launch_after_min"] = round((parse_time(controller["first_launch"]) - start).total_seconds() / 60, 1)
    return {
        "benchmark": bench,
        "status": meta.get("status"),
        "started": start.isoformat() if start else None,
        "finished": meta.get("finished"),
        "wall_min": round(wall / 60, 1) if wall else None,
        "trials": len(done),
        "unfinished": len(inside) - len(done),
        "install": installs,
        "pool_errors": sum(1 for t in done if t["pool_error"]),
        "phase_median_s": {p: median([t["phases"][p] for t in done if t["phases"][p] is not None]) for p in PHASES},
        "minutes_at_k_running": running_minutes(done, start, end) if start else {},
        "effective_concurrency": round(sum((t["ended"] - t["started"]).total_seconds() for t in done) / wall, 2) if wall else None,
        "controller": controller,
    }


def describe(rid: str, root: str, steps: dict[str, dict]) -> list[str]:
    lines = [f"{rid}  ({root})"]
    for name, s in steps.items():
        when = f"{s['started'][11:16]}–{s['finished'][11:16] if s['finished'] else 'now'} UTC" if s["started"] else "no start"
        lines.append(
            f"  {name}  {s['benchmark'].rsplit('-', 1)[-1]}  {when}, {s['wall_min']} min ({s['status']}): "
            f"{s['trials']} trials, {s['unfinished']} unfinished, {s['pool_errors']} pool errors; "
            f"install {', '.join(f'{k} {v}' for k, v in sorted(s['install'].items())) or '—'}"
        )
        lines.append("      phase medians (s): " + ", ".join(f"{p} {v if v is not None else '—'}" for p, v in s["phase_median_s"].items()))
        lines.append(
            "      minutes at k running: " + (", ".join(f"{k}: {v}" for k, v in s["minutes_at_k_running"].items()) or "—")
            + f"; effective concurrency {s['effective_concurrency']}"
        )
        c = s["controller"]
        if c is None:
            lines.append("      controller: no Session log")
        else:
            lines.append(
                f"      controller{'' if c['controller_only'] else ' (with its subagents: no trace positions)'}: "
                f"run_subagent {c['run_subagent']}, input_subagent {c['input_subagent']}, subagent notices {c['subagent_notices']}"
                + (f", first launch after {c['first_launch_after_min']} min" if c.get("first_launch_after_min") is not None else "")
                + f"; notice to next launch: {c['notices_followed_by_a_launch']} followed, "
                f"median {c['notice_to_launch_median_s']} s, max {c['notice_to_launch_max_s']} s"
            )
    return lines


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("out", nargs="+", help="a replica's output directory (or its state/)")
    parser.add_argument("--root", help="the data root, when a single replica is given and its root moved")
    parser.add_argument("--json", help="also write the numbers to this file")
    args = parser.parse_args()
    if args.root and len(args.out) > 1:
        parser.error("--root goes with a single replica")

    report = {}
    for out in args.out:
        state = out if os.path.isfile(os.path.join(out, "meta.json")) else os.path.join(out, "state")
        meta = load_json(os.path.join(state, "meta.json"), {}) or {}
        root = args.root or meta.get("data_root")
        if not root:
            print(f"timeline.py: {state}/meta.json names no data root; pass --root", file=sys.stderr)
            return 2
        rid = meta.get("replica_id") or os.path.basename(os.path.normpath(out))
        trials_by_bench: dict[str, list[dict]] = {}
        steps = {}
        for name in STEPS:
            record = step_timeline(state, root, name, trials_by_bench)
            if record is not None:
                steps[name] = record
        report[rid] = {"data_root": root, "concurrency_by_step": meta.get("concurrency_by_step"), "steps": steps}
        print("\n".join(describe(rid, root, steps)))
    if args.json:
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
    return 0


if __name__ == "__main__":
    sys.exit(main())
