"""Regression checks without model calls, Docker or third-party dependencies.

    python3 tools/gdpevo/protocol/test_aggregate.py
"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).with_name("aggregate.py")


class AggregateTests(unittest.TestCase):
    def aggregate(self, steps):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            command = [sys.executable, str(SCRIPT), "--out", str(root / "out")]
            for index, step in enumerate(steps):
                replica = {
                    "replica_id": f"r{index + 1}",
                    "steps": {} if step is None else {"T0": {"trials": step}},
                    "totals": {
                        "trial_cost_usd": 0, "host_cost_usd": 0, "total_usd": 0,
                        "complete": True, "wall_s": 0, "trial_count": len(step or []),
                    },
                }
                path = root / f"r{index + 1}.json"
                path.write_text(json.dumps(replica), encoding="utf-8")
                command.extend(["--replica", str(path)])
            subprocess.run(command, check=True, capture_output=True, text=True)
            return json.loads((root / "out/summary.json").read_text(encoding="utf-8"))

    def trial(self, task, reward, started="2026-01-01T00:00:00Z"):
        return {"task": f"tg003-test-{task:03d}", "reward": reward, "started": started}

    def test_missing_middle_trial_keeps_replica_alignment(self):
        summary = self.aggregate([
            [self.trial(1, 1), self.trial(2, 0)],
            [self.trial(2, 1)],
            [self.trial(1, 0), self.trial(2, 1)],
        ])
        task = summary["per_task"]["tg003-test-001"]["T0"]
        self.assertEqual(task["scores"], [100, None, 0])
        self.assertEqual(task["missing"], 1)
        self.assertEqual(task["acc@3"], 50)
        self.assertEqual(task["std@3"], 50)
        for aggregate in [summary["overall"]["T0"], summary["per_group"]["tg003"]["T0"]]:
            self.assertEqual(aggregate["per_replica_mean"], [50, 100, 50])
            self.assertEqual(aggregate["replica_std"], 23.57)

    def test_missing_step_preserves_an_empty_replica_slot(self):
        summary = self.aggregate([[self.trial(1, 1)], None, [self.trial(1, 0)]])
        self.assertEqual(summary["per_task"]["tg003-test-001"]["T0"]["missing"], 1)
        self.assertEqual(summary["overall"]["T0"]["per_replica_mean"], [100, None, 0])
        self.assertEqual(summary["overall"]["T0"]["replica_std"], 50)

    def test_unscored_trial_and_absent_trial_both_count_as_missing(self):
        summary = self.aggregate([[self.trial(1, None)], [], [self.trial(1, None)]])
        task = summary["per_task"]["tg003-test-001"]["T0"]
        self.assertEqual(task["scores"], [None, None, None])
        self.assertEqual(task["missing"], 3)
        self.assertIsNone(task["acc@3"])
        self.assertIsNone(task["std@3"])
        self.assertNotIn("T0", summary["overall"])

    def test_complete_replicas_still_use_latest_trial(self):
        summary = self.aggregate([
            [self.trial(1, 1, "2026-01-02T00:00:00Z"), self.trial(1, 0)],
            [self.trial(1, 0)],
            [self.trial(1, 0.5)],
        ])
        task = summary["per_task"]["tg003-test-001"]["T0"]
        self.assertEqual(task["scores"], [100, 0, 50])
        self.assertEqual(task["missing"], 0)
        self.assertEqual(task["acc@3"], 50)
        self.assertEqual(task["std@3"], 40.82)
        self.assertEqual(summary["overall"]["T0"]["per_replica_mean"], [100, 0, 50])


if __name__ == "__main__":
    unittest.main()
