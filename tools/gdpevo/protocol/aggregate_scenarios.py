#!/usr/bin/env python3
"""Exercise replica accounting through the aggregation CLI.

Run from the repository root:
    python3 tools/gdpevo/protocol/aggregate_scenarios.py

Given the published calibration replicas and a small, independently specified score
matrix, remove observations, interrupt steps, append unsuccessful retries, and
distinguish missing execution from a completed task's zero reward.
When aggregate.py writes JSON and Markdown, including a second write to the same
output directory, inspect those files through the public CLI contract.
Then complete data keeps its published numbers; missing observations retain their
replica positions and invalidate dependent means without hiding diagnostic records.
Conflicting run identities, ambiguous retries, and invalid scores are rejected while
the existing output stays intact.

Only the standard library is used. All generated inputs and reports are temporary;
the published fixtures remain unchanged. Failures are reported explicitly.
"""

from __future__ import annotations

import copy
import json
import math
import os
import subprocess
import sys
import tempfile
import threading
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
AGGREGATE = Path(__file__).with_name("aggregate.py")
PUBLISHED = REPO / "results" / "gdpevo-rsi-calibration"
STEPS = ("B0", "T0", "O1", "T1")
TRAIN_STEPS = ("B0", "O1")
TEST_STEPS = ("T0", "T1")
SCORES = {
    "tg003-{}-001": [12.5, 25.0, 37.5],
    "tg003-{}-002": [37.5, 50.0, 62.5],
    "tg005-{}-001": [62.5, 75.0, 87.5],
    "tg005-{}-002": [25.0, 50.0, 75.0],
}


def average(values: list[float]) -> float:
    return round(sum(values) / len(values), 2)


def deviation(values: list[float]) -> float:
    center = sum(values) / len(values)
    return round(math.sqrt(sum((value - center) ** 2 for value in values) / len(values)), 2)


def fixtures() -> tuple[list[dict], dict, dict]:
    expected = {
        step: {
            task.format("train" if step in TRAIN_STEPS else "test"):
                [value + (12.5 if step in ("O1", "T1") else 0) for value in values]
            for task, values in SCORES.items()
        }
        for step in STEPS
    }
    scoreboard = {
        step: [average([values[index] for values in tasks.values()]) for index in range(3)]
        for step, tasks in expected.items()
    }
    replicas = []
    for index in range(3):
        steps = {}
        for step, tasks in expected.items():
            evaluation = {
                "score": scoreboard[step][index],
                "cases": [{"case": f"CASE-{number:03d}-{task}"} for number, task in enumerate(tasks, 1)],
            }
            steps[step] = {
                "status": "completed", "evaluation": evaluation,
                "evaluations": [copy.deepcopy(evaluation)],
                "score_from_trials": scoreboard[step][index],
                "trial_count": len(tasks), "scored": len(tasks),
                "trials": [
                    {"task": task, "started": "2026-10-16T09:00:00Z", "reward": values[index] / 100}
                    for task, values in tasks.items()
                ],
            }
        replicas.append({
            "replica_id": f"r{index + 1}", "model": {"provider": "scenario", "model_id": "fixed"},
            "test_thinking": "none", "controller_thinking": "none", "concurrency": 1,
            "steps": steps, "aborted": False,
            "totals": {"trial_cost_usd": 0.0, "host_cost_usd": 0.0, "total_usd": 0.0,
                       "complete": True, "wall_s": 0.0, "trial_count": 16},
        })
    return replicas, expected, scoreboard


def expect(document, path: tuple, expected, failures: list[str]) -> None:
    actual = document
    try:
        for key in path:
            actual = actual[key]
    except (KeyError, IndexError, TypeError):
        actual = "<missing>"
    if actual != expected:
        failures.append(f"{'.'.join(map(str, path)) or '<report>'}: expected {expected!r}, got {actual!r}")


def check_matrix(summary: dict, expected: dict, scoreboard: dict, failures: list[str]) -> None:
    expect(summary, ("n_replicas",), 3, failures)
    all_tasks = set().union(*(set(tasks) for tasks in expected.values()))
    expect(sorted(summary.get("per_task", {})), (), sorted(all_tasks), failures)
    groups = sorted({task.split("-")[0] for task in all_tasks})
    expect(sorted(summary.get("per_group", {})), (), groups, failures)
    for group in groups:
        expect(summary, ("per_group", group, "n_tasks"), sum(t.startswith(group + "-") for t in all_tasks), failures)
    for step, tasks in expected.items():
        for task, values in tasks.items():
            prefix = ("per_task", task, step)
            complete = None not in values
            for key, value in {
                "scores": values, "missing": values.count(None),
                "acc@3": average(values) if complete else None,
                "std@3": deviation(values) if complete else None,
            }.items():
                expect(summary, prefix + (key,), value, failures)
        if not tasks:
            continue
        for group in [None, *groups]:
            selected = [values for task, values in tasks.items() if group is None or task.startswith(group + "-")]
            if not selected:
                continue
            prefix = ("overall", step) if group is None else ("per_group", group, step)
            missing = sum(values.count(None) for values in selected)
            columns = [[values[index] for values in selected] for index in range(3)]
            means = [None if None in column else average(column) for column in columns]
            for key, value in {
                "n_tasks": len(selected), "missing": missing, "per_replica_mean": means,
                "mean_acc@3": average([average(values) for values in selected]) if not missing else None,
                "mean_std@3": average([deviation(values) for values in selected]) if not missing else None,
                "replica_std": deviation(means) if not missing else None,
            }.items():
                expect(summary, prefix + (key,), value, failures)
        values = scoreboard[step]
        for key, value in {
            "scoreboard_scores": values,
            "scoreboard_mean": average(values) if None not in values else None,
            "scoreboard_std": deviation(values) if None not in values else None,
        }.items():
            expect(summary, ("overall", step, key), value, failures)


def compare_published(actual, published, failures: list[str], path: tuple = ()) -> None:
    """Compare every published numeric/null leaf, allowing new diagnostic fields."""
    if isinstance(published, dict):
        for key, value in published.items():
            if path or key not in ("generated_at", "notes"):
                compare_published(actual, value, failures, path + (key,))
    elif isinstance(published, list):
        for index, value in enumerate(published):
            compare_published(actual, value, failures, path + (index,))
    elif published is None or isinstance(published, (int, float)):
        expect(actual, path, published, failures)


def recollected_input(root: Path) -> bool:
    """A FIFO holds the next read while the collector replaces an already read input."""
    if not hasattr(os, "mkfifo"):
        print("SKIP recollected-input: requires POSIX FIFOs")
        return True
    inputs = root / "recollected-input"
    inputs.mkdir()
    replicas, expected, scoreboard = fixtures()
    records = [json.dumps(replica).encode() for replica in replicas]
    first, second, third = (inputs / f"r{index}.json" for index in range(3))
    first.write_bytes(records[0])
    os.mkfifo(second)
    third.write_bytes(records[2])
    output = inputs / "report"
    failures = []

    def recollect() -> None:
        try:
            with second.open("wb") as pipe:
                second.unlink()
                second.write_bytes(records[1])
                replicas[0]["steps"]["B0"]["trials"][0]["reward"] = 0
                first.write_text(json.dumps(replicas[0]), encoding="utf-8")
                pipe.write(records[1])
        except OSError as error:
            failures.append(f"recollection failed: {error}")

    writer = threading.Thread(target=recollect, daemon=True)
    writer.start()
    command = [sys.executable, str(AGGREGATE), "--out", str(output)]
    for source in (first, second, third):
        command.extend(("--replica", str(source)))
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=10)
        if result.returncode:
            failures.append(f"CLI failed: {result.stderr}")
        else:
            check_matrix(json.loads((output / "summary.json").read_text()), expected, scoreboard, failures)
            if (output / "replicas" / "r1.json").read_bytes() != records[0]:
                failures.append("published replica differs from the bytes used for aggregation")
    except subprocess.TimeoutExpired:
        failures.append("CLI did not finish after recollection")
    finally:
        # Release a writer waiting on an input the CLI rejected before opening.
        fd = os.open(second, os.O_RDWR | os.O_NONBLOCK)
        writer.join(timeout=1)
        os.close(fd)
    print(f"{'FAIL' if failures else 'PASS'} recollected-input")
    for failure in failures:
        print(f"  {failure}")
    return not failures


def run(root: Path, name: str, replicas: list[dict], expected=None, scoreboard=None,
        *, published=None, output: Path | None = None, incomplete_test=False) -> bool:
    inputs = root / name
    inputs.mkdir()
    output = output or inputs / "report"
    command = [sys.executable, str(AGGREGATE), "--out", str(output)]
    for index, replica in enumerate(replicas):
        source = inputs / f"input-{index}.json"
        source.write_text(json.dumps(replica), encoding="utf-8")
        command.extend(("--replica", str(source)))
    result = subprocess.run(command, capture_output=True, text=True)
    failures = []
    if result.returncode:
        failures.append(f"CLI exit {result.returncode}: {result.stderr.strip()[-800:]}")
    else:
        try:
            summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))
            markdown = (output / "README.md").read_text(encoding="utf-8")
        except (OSError, ValueError) as exc:
            failures.append(f"report could not be read: {exc}")
        else:
            if published is not None:
                compare_published(summary, published, failures)
            else:
                check_matrix(summary, expected, scoreboard, failures)
            for index, replica in enumerate(replicas):
                copied = output / "replicas" / f"{replica['replica_id']}.json"
                try:
                    expect(json.loads(copied.read_text(encoding="utf-8")), (), replica, failures)
                except (OSError, ValueError) as exc:
                    failures.append(f"Copied replica could not be read: {exc}")
                for step, state in replica["steps"].items():
                    expect(summary, ("replicas", index, "steps", step, "score_from_trials"),
                           state.get("score_from_trials"), failures)
            if not markdown.startswith("# GDPevo RSI calibration\n"):
                failures.append("Markdown report is missing its title")
            if incomplete_test:
                if "—" not in markdown:
                    failures.append("Markdown report does not display missing values as —")
                if "Test transfer:" in markdown:
                    failures.append("Markdown claims Test transfer from an incomplete test matrix")
    if failures:
        print(f"FAIL {name}")
        for failure in sorted(failures, key=lambda failure: failure.endswith("got '<missing>'"))[:5]:
            print(f"  {failure}")
        if len(failures) > 5:
            print(f"  ... {len(failures) - 5} more mismatches")
        return False
    print(f"PASS {name}")
    return True


def reject_duplicates(root: Path, name: str) -> bool:
    inputs = root / name
    inputs.mkdir()
    output = inputs / "report"
    (output / "replicas").mkdir(parents=True)
    for relative in ("sentinel", "summary.json", "README.md", "replicas/r1.json"):
        (output / relative).write_text(f"existing {relative}\n", encoding="utf-8")
    before = {path.relative_to(output): path.read_bytes() for path in output.rglob("*") if path.is_file()}
    replica = fixtures()[0][0]
    source = inputs / "first.json"
    source.write_text(json.dumps(replica), encoding="utf-8")
    second = source
    if name == "duplicate-id-in-distinct-files":
        second = inputs / "second.json"
        second.write_text(json.dumps(replica), encoding="utf-8")
    elif name == "duplicate-fallback-directory-id":
        replica.pop("replica_id")
        source = inputs / "first" / "r1" / "replica.json"
        second = inputs / "second" / "r1" / "replica.json"
        for path in (source, second):
            path.parent.mkdir(parents=True)
            path.write_text(json.dumps(replica), encoding="utf-8")
    result = subprocess.run(
        [sys.executable, str(AGGREGATE), "--out", str(output),
         "--replica", str(source), "--replica", str(second)],
        capture_output=True, text=True,
    )
    failures = []
    if result.returncode == 0:
        failures.append("CLI accepted duplicate replica identities")
    if "duplicate" not in result.stderr.lower() or "r1" not in result.stderr:
        failures.append(f"CLI did not identify the duplicate r1: {result.stderr.strip()[-800:]}")
    after = {path.relative_to(output): path.read_bytes() for path in output.rglob("*") if path.is_file()}
    if after != before:
        failures.append("Rejected inputs changed the existing output directory")
    print(f"{'FAIL' if failures else 'PASS'} {name}")
    for failure in failures:
        print(f"  {failure}")
    return not failures


def reject(root: Path, name: str, replicas: list[dict], detail: str) -> bool:
    """Reject an invalid input before replacing any part of an existing real report."""
    inputs = root / name
    inputs.mkdir()
    output = inputs / "report"
    baseline = [sys.executable, str(AGGREGATE), "--out", str(output)]
    command = baseline.copy()
    for index, (original, replica) in enumerate(zip(fixtures()[0], replicas)):
        for label, record, invocation in (("baseline", original, baseline), ("input", replica, command)):
            path = inputs / f"{label}-{index}.json"
            path.write_text(json.dumps(record), encoding="utf-8")
            invocation.extend(("--replica", str(path)))
    setup = subprocess.run(baseline, capture_output=True, text=True)
    if setup.returncode:
        print(f"FAIL {name}: could not create the existing report: {setup.stderr.strip()[-500:]}")
        return False
    before = {path.relative_to(output): path.read_bytes() for path in output.rglob("*") if path.is_file()}
    result = subprocess.run(command, capture_output=True, text=True)
    failures = []
    if result.returncode == 0:
        failures.append("CLI accepted invalid records")
    if "Traceback (most recent call last)" in result.stderr:
        failures.append("CLI raised a traceback instead of reporting the invalid input")
    if detail.lower() not in result.stderr.lower():
        failures.append(f"CLI did not identify {detail!r}: {result.stderr.strip()[-500:]}")
    after = {path.relative_to(output): path.read_bytes() for path in output.rglob("*") if path.is_file()}
    if before != after:
        failures.append("Rejected inputs changed the existing report or copied replicas")
    print(f"{'FAIL' if failures else 'PASS'} {name}")
    for failure in failures:
        print(f"  {failure}")
    return not failures


def comparison_scenarios(root: Path) -> list[bool]:
    outcomes = []
    identity = {
        "commit": ("a" * 40, "b" * 40),
        "model": ({"provider": "scenario", "model_id": "fixed"}, {"provider": "other", "model_id": "fixed"}),
        "test_thinking": ("none", "high"),
        "controller_thinking": ("none", "low"),
        "concurrency": (1, 2),
        "limit_usd": (20.0, 10.0),
    }
    for field, (initial, changed) in identity.items():
        replicas, expected, scoreboard = fixtures()
        for replica in replicas:
            replica[field] = copy.deepcopy(initial)
        replicas[1][field] = changed
        outcomes.append(reject(root, f"mixed-{field}", replicas, field))
        replicas[1].pop(field)
        outcomes.append(reject(root, f"partly-missing-{field}", replicas, field))
        for replica in replicas:
            replica.pop(field, None)
        outcomes.append(run(root, f"all-missing-{field}", replicas, expected, scoreboard))
        replicas[1][field] = None
        outcomes.append(reject(root, f"missing-versus-null-{field}", replicas, field))
    replicas, _, _ = fixtures()
    replicas[1]["model"]["model_id"] = "other-model"
    outcomes.append(reject(root, "mixed-model-id", replicas, "model"))
    replicas, expected, scoreboard = fixtures()
    for replica, rid in zip(replicas, ("A", "replica_02", "-3-")):
        replica["replica_id"] = rid
    outcomes.append(run(root, "valid-driver-replica-ids", replicas, expected, scoreboard))
    replicas, _, _ = fixtures()
    replicas[1]["replica_id"] = "R1"
    outcomes.append(reject(root, "case-insensitive-replica-collision", replicas, "replica"))
    for label, rid in (("empty", ""), ("null", None), ("number", 2), ("boolean", True),
                       ("dot", "."), ("parent", ".."), ("slash", "../escape"),
                       ("backslash", "a\\b"), ("space", "r 2"), ("unicode", "réplica")):
        replicas, _, _ = fixtures()
        replicas[1]["replica_id"] = rid
        outcomes.append(reject(root, f"invalid-replica-id-{label}", replicas, "replica"))
    return outcomes


def retry_scenarios(root: Path) -> list[bool]:
    outcomes = []
    task = "tg003-test-001"
    # Each pair is independently ordered here by its UTC instant, oldest first.
    pairs = (
        ("offset", "2026-10-16T09:00:00Z", "2026-10-16T05:30:00-04:00"),
        ("fraction", "2026-10-16T09:00:00Z", "2026-10-16T09:00:00.000001Z"),
        ("naive-utc", "2026-10-16T09:00:00", "2026-10-16T09:00:00.000001+00:00"),
        ("missing", None, "2026-10-16T09:00:00Z"),
    )
    for label, earlier, later in pairs:
        for reverse in (False, True):
            replicas, expected, scoreboard = fixtures()
            state = replicas[1]["steps"]["T1"]
            retries = [{"task": task, "started": earlier, "reward": 0.1},
                       {"task": task, "started": later, "reward": 0.9}]
            state["trials"] = [trial for trial in state["trials"] if trial["task"] != task] + (retries[::-1] if reverse else retries)
            state["evaluation"] = None
            state["score_from_trials"] = 50.0
            expected["T1"][task][1] = 90.0
            scoreboard["T1"][1] = average([values[1] for values in expected["T1"].values()])
            outcomes.append(run(root, f"latest-retry-{label}-{'reverse' if reverse else 'forward'}", replicas, expected, scoreboard))
    for label, change in (("reward", {"reward": 0.9}), ("validity", {"status": "server_failed", "requests": 1})):
        for reverse in (False, True):
            replicas, _, _ = fixtures()
            state = replicas[1]["steps"]["T1"]
            original = next(trial for trial in state["trials"] if trial["task"] == task)
            retry = {**original, "started": "2026-10-16T05:00:00-04:00", **change}
            state["trials"] = ([retry] + state["trials"]) if reverse else (state["trials"] + [retry])
            outcomes.append(reject(root, f"same-instant-conflicting-{label}-{'reverse' if reverse else 'forward'}", replicas, task))
    replicas, expected, scoreboard = fixtures()
    state = replicas[1]["steps"]["T1"]
    original = next(trial for trial in state["trials"] if trial["task"] == task)
    state["trials"].append({**original, "started": "2026-10-16T05:00:00-04:00"})
    outcomes.append(run(root, "same-instant-consistent-reward", replicas, expected, scoreboard))
    for reverse in (False, True):
        replicas, expected, scoreboard = fixtures()
        state = replicas[1]["steps"]["T1"]
        retries = [{"task": task, "started": "2026-10-16T09:00:00Z", "reward": 0.1},
                   {"task": task, "started": "2026-10-16T05:00:00-04:00", "reward": 0.5},
                   {"task": task, "started": "2026-10-16T09:30:00Z", "reward": 0.9}]
        state["trials"] = [trial for trial in state["trials"] if trial["task"] != task] + (retries[::-1] if reverse else retries)
        state["evaluation"] = None
        state["score_from_trials"] = 50.0
        expected["T1"][task][1] = 90.0
        scoreboard["T1"][1] = average([values[1] for values in expected["T1"].values()])
        outcomes.append(run(root, f"superseded-conflict-{'reverse' if reverse else 'forward'}", replicas, expected, scoreboard))
    for conflict in (False, True):
        replicas, expected, scoreboard = fixtures()
        state = replicas[1]["steps"]["T1"]
        original = next(trial for trial in state["trials"] if trial["task"] == task)
        original.pop("started")
        state["trials"].append({**original, "started": None, "reward": 0.9 if conflict else original["reward"]})
        if conflict:
            outcomes.append(reject(root, "unknown-time-conflicting-rewards", replicas, task))
        else:
            outcomes.append(run(root, "unknown-time-consistent-rewards", replicas, expected, scoreboard))
    return outcomes


def numeric_scenarios(root: Path) -> list[bool]:
    outcomes = []
    values = (("nan", float("nan")), ("infinity", float("inf")), ("negative-infinity", -float("inf")),
              ("text", "0.5"), ("true", True), ("false", False), ("negative", -0.1), ("above-maximum", 1.1))
    for field in ("reward", "evaluation-score", "trial-score"):
        for label, value in values:
            replicas, _, _ = fixtures()
            state = replicas[1]["steps"]["T1"]
            if field == "reward":
                state["trials"][0]["reward"] = value
            else:
                if label == "above-maximum":
                    value = 101.0
                if field == "evaluation-score":
                    state["evaluation"]["score"] = value
                else:
                    state["score_from_trials"] = value
            outcomes.append(reject(root, f"invalid-{field}-{label}", replicas, "reward" if field == "reward" else "score"))
    return outcomes


def grouped_fallback(root: Path) -> bool:
    replicas, _, _ = fixtures()
    tasks = [f"tg003-train-{number:03d}" for number in range(1, 6)]
    # PR #5 records continuing-session usage only on the first task. Its collector's
    # request-filtered mean is 20; the five completed tasks independently average 84.
    expected = {"B0": {task: [None] * 3 for task in tasks}, "T0": {},
                "O1": {task: [score] * 3 for task, score in zip(tasks, (20.0, 100.0, 100.0, 100.0, 100.0))}, "T1": {}}
    scoreboard = {"B0": [None] * 3, "T0": [None] * 3, "O1": [84.0] * 3, "T1": [None] * 3}
    for replica in replicas:
        replica["steps"] = {"O1": {
            "status": "completed", "evaluation": None, "evaluations": [],
            "score_from_trials": 20.0, "trial_count": 5, "scored": 1,
            "trials": [{"task": task, "started": "2026-10-16T09:00:00Z", "reward": reward,
                        "requests": 100 if index == 0 else 0, "status": "completed", "group_complete": True}
                       for index, (task, reward) in enumerate(zip(tasks, (0.2, 1.0, 1.0, 1.0, 1.0)))],
        }}
    return run(root, "grouped-collector-fallback", replicas, expected, scoreboard)


def remove_task(replicas, expected, scoreboard, step, task, index, *, reward_only=False):
    state = replicas[index]["steps"][step]
    if reward_only:
        for trial in state["trials"]:
            if trial["task"] == task:
                trial["reward"] = None
    else:
        state["trials"] = [trial for trial in state["trials"] if trial["task"] != task]
    state["evaluation"]["score"] = state["score_from_trials"] = None
    state["trial_count"] = len(state["trials"])
    state["scored"] = sum(trial.get("reward") is not None for trial in state["trials"])
    expected[step][task][index] = None
    scoreboard[step][index] = None


def main() -> int:
    outcomes = []
    with tempfile.TemporaryDirectory(prefix="gdpevo-aggregate-") as temporary:
        root = Path(temporary)
        released = [json.loads((PUBLISHED / "replicas" / f"r{index}.json").read_text(encoding="utf-8")) for index in (1, 2, 3)]
        reference = json.loads((PUBLISHED / "summary.json").read_text(encoding="utf-8"))
        outcomes.append(run(root, "published-calibration", released, published=reference))
        outcomes.append(run(root, "complete-matrix", *fixtures()))
        outcomes.extend(comparison_scenarios(root))
        outcomes.extend(retry_scenarios(root))
        outcomes.extend(numeric_scenarios(root))
        outcomes.append(grouped_fallback(root))
        for source in ("current", "historical", "sibling"):
            replicas = fixtures()[0]
            state = replicas[1]["steps"]["B0" if source == "sibling" else "O1"]
            evaluation = state["evaluations"][0] if source == "historical" else state["evaluation"]
            evaluation["cases"].append({"case": "CASE-006-tg024-train", "score": None})
            outcomes.append(reject(root, f"unresolved-group-roster-{source}", replicas, "tg024-train"))
        for name in ("duplicate-input-path", "duplicate-id-in-distinct-files", "duplicate-fallback-directory-id"):
            outcomes.append(reject_duplicates(root, name))
        replicas, expected, scoreboard = fixtures()
        for replica in replicas:
            for state in replica["steps"].values():
                state["evaluation"]["cases"].append({"case": None, "score": None})
                state["evaluations"][0]["cases"].append({"case": None, "score": None})
        outcomes.append(run(root, "unidentified-scoreboard-cases", replicas, expected, scoreboard))
        replicas, expected, scoreboard = fixtures()
        for replica in replicas:
            for state in replica["steps"].values():
                state["evaluation"] = None
        outcomes.append(run(root, "complete-trial-score-fallback", replicas, expected, scoreboard))
        task = "tg003-test-001"
        for index, position in enumerate(("first", "middle", "last")):
            replicas, expected, scoreboard = fixtures()
            remove_task(replicas, expected, scoreboard, "T1", task, index)
            outcomes.append(run(root, f"missing-{position}-replica-task", replicas, expected, scoreboard, incomplete_test=True))
        replicas, expected, scoreboard = fixtures()
        replicas[1]["steps"].pop("T1")
        replicas[1]["aborted"] = True
        for values in expected["T1"].values():
            values[1] = None
        scoreboard["T1"][1] = None
        outcomes.append(run(root, "missing-whole-step", replicas, expected, scoreboard, incomplete_test=True))
        replicas, expected, scoreboard = fixtures()
        remove_task(replicas, expected, scoreboard, "T1", task, 1, reward_only=True)
        outcomes.append(run(root, "present-trial-without-reward", replicas, expected, scoreboard, incomplete_test=True))
        replicas, expected, scoreboard = fixtures()
        remove_task(replicas, expected, scoreboard, "T1", task, 1)
        state = replicas[1]["steps"]["T1"]
        state.update(status="aborted", evaluation=None, evaluations=[])
        state["score_from_trials"] = average([values[1] for values in expected["T1"].values() if values[1] is not None])
        replicas[1]["aborted"] = True
        outcomes.append(run(root, "aborted-partial-trial-score-fallback", replicas, expected, scoreboard, incomplete_test=True))
        for discovery in ("current-scoreboard", "historical-scoreboard", "sibling-step"):
            replicas, expected, scoreboard = fixtures()
            for step in (("T1",) if discovery == "sibling-step" else TEST_STEPS):
                for index, replica in enumerate(replicas):
                    remove_task(replicas, expected, scoreboard, step, task, index)
                    state = replica["steps"][step]
                    if discovery != "current-scoreboard":
                        state["evaluation"]["cases"] = [case for case in state["evaluation"]["cases"] if not case["case"].endswith(task)]
                    if discovery != "historical-scoreboard":
                        state["evaluations"] = []
            outcomes.append(run(root, f"task-discovered-from-{discovery}", replicas, expected, scoreboard, incomplete_test=True))
        replicas, expected, scoreboard = fixtures()
        state = replicas[1]["steps"]["T1"]
        state["trials"].extend([
            {"task": task, "started": "2026-10-16T11:00:00Z", "reward": None},
            {"task": task, "started": "2026-10-16T10:00:00Z", "reward": 1.0},
        ])
        state["evaluation"]["score"] = state["score_from_trials"] = None
        expected["T1"][task][1] = scoreboard["T1"][1] = None
        outcomes.append(run(root, "latest-retry-is-unscored", replicas, expected, scoreboard, incomplete_test=True))
        for name, metadata in (
            ("server-failed-latest-trial", {"status": "server_failed", "requests": 1}),
            ("config-failed-latest-trial", {"status": "config_failed", "requests": 1}),
            ("zero-request-latest-trial", {"status": "completed", "requests": 0}),
            ("incomplete-group-zero-request", {"status": "completed", "requests": 0, "group_complete": False}),
            ("failed-group-completion", {"status": "server_failed", "requests": 0, "group_complete": True}),
        ):
            replicas, expected, scoreboard = fixtures()
            state = replicas[1]["steps"]["T1"]
            state["trials"].append({"task": task, "started": "2026-10-16T11:00:00Z", "reward": 1.0, **metadata})
            state["trial_count"] = len(state["trials"])
            state["evaluation"] = None
            expected["T1"][task][1] = scoreboard["T1"][1] = None
            outcomes.append(run(root, name, replicas, expected, scoreboard, incomplete_test=True))
        replicas, expected, scoreboard = fixtures()
        state = replicas[1]["steps"]["T1"]
        state["trials"][0].update(status="completed", requests=1, reward=0.0)
        expected["T1"][task][1] = 0.0
        state["evaluation"] = None
        state["score_from_trials"] = scoreboard["T1"][1] = average([values[1] for values in expected["T1"].values()])
        outcomes.append(run(root, "completed-zero-reward", replicas, expected, scoreboard))
        replicas, expected, scoreboard = fixtures()
        for replica in replicas:
            state = replica["steps"]["T1"]
            for number, trial in enumerate(state["trials"]):
                trial.update(status="completed", group_complete=True, requests=1 if number % 2 == 0 else 0)
            state["evaluation"] = None
        outcomes.append(run(root, "completed-group-shared-requests", replicas, expected, scoreboard))
        for discovered in (False, True):
            replicas, expected, scoreboard = fixtures()
            for replica in replicas:
                replica["aborted"] = True
                replica["totals"]["wall_s"] = None
                replica["totals"]["trial_count"] = 0
                if not discovered:
                    replica["steps"] = {}
                else:
                    for state in replica["steps"].values():
                        state.update(status="aborted", trials=[], evaluation=None, score_from_trials=None, trial_count=0, scored=0)
            expected = {step: {task: [None] * 3 for task in tasks} if discovered else {} for step, tasks in expected.items()}
            scoreboard = {step: [None] * 3 for step in STEPS}
            outcomes.append(run(root, "aborted-after-discovery" if discovered else "aborted-before-discovery",
                                replicas, expected, scoreboard, incomplete_test=True))
        destination = root / "reused-report"
        replicas, expected, scoreboard = fixtures()
        remove_task(replicas, expected, scoreboard, "T1", task, 0)
        outcomes.append(run(root, "first-write-incomplete", replicas, expected, scoreboard,
                            output=destination, incomplete_test=True))
        outcomes.append(run(root, "rewrite-complete", *fixtures(), output=destination))
        outcomes.append(run(root, "rewrite-incomplete", replicas, expected, scoreboard,
                            output=destination, incomplete_test=True))
        outcomes.append(recollected_input(root))
    print(f"{sum(outcomes)}/{len(outcomes)} scenarios passed")
    return 0 if all(outcomes) else 1


if __name__ == "__main__":
    sys.exit(main())
