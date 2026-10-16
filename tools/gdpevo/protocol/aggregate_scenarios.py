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
Duplicate replica identities are rejected while the existing output stays intact.

Only the standard library is used. All generated inputs and reports are temporary;
the published fixtures remain unchanged. Failures are reported explicitly.
"""

from __future__ import annotations

import copy
import json
import math
import subprocess
import sys
import tempfile
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


def run(root: Path, name: str, replicas: list[dict], expected=None, scoreboard=None,
        *, published=None, output: Path | None = None, incomplete_test=False) -> bool:
    inputs = root / name
    inputs.mkdir()
    output = output or inputs / "report"
    command = [sys.executable, str(AGGREGATE), "--out", str(output)]
    for replica in replicas:
        source = inputs / f"{replica['replica_id']}.json"
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
    print(f"{sum(outcomes)}/{len(outcomes)} scenarios passed")
    return 0 if all(outcomes) else 1


if __name__ == "__main__":
    sys.exit(main())
