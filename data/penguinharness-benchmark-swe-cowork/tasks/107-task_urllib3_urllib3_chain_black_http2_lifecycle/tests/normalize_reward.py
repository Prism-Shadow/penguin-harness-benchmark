#!/usr/bin/env python3
"""Normalize historical verifier outputs to Harbor's reward.json contract."""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path


def numeric_payload(value):
    if not isinstance(value, dict):
        return None
    result = {
        str(key): number
        for key, number in value.items()
        if isinstance(number, (int, float))
        and not isinstance(number, bool)
        and math.isfinite(float(number))
    }
    return result if "reward" in result else None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--exit-code", type=int, required=True)
    args = parser.parse_args()
    root = Path(os.environ.get("VERIFIER_LOG_DIR", "/logs/verifier"))
    root.mkdir(parents=True, exist_ok=True)
    selected = None
    source = None
    errors = []
    source_payloads = []
    non_numeric_fields = {}
    # reward.json is our output from a previous invocation. Never use it as
    # this invocation's source: the grader writes the current result to
    # rewards.json. Removing it also makes a missing source fail closed.
    stale = root / "reward.json"
    if stale.exists():
        stale.unlink()
    candidate = root / "rewards.json"
    if candidate.is_file() and candidate.stat().st_size:
        try:
            raw = candidate.read_bytes()
            raw_sha256 = hashlib.sha256(raw).hexdigest()
            archive_name = "source-" + candidate.stem + "." + raw_sha256 + ".json"
            (root / archive_name).write_bytes(raw)
            source_payloads.append({"source": candidate.name, "archive": archive_name,
                                    "sha256": raw_sha256, "bytes": len(raw)})
            original_payload = json.loads(raw)
            selected = numeric_payload(original_payload)
        except (OSError, ValueError, TypeError) as exc:
            errors.append(f"{candidate.name}: {type(exc).__name__}: {exc}")
        if selected is not None:
            source = candidate.name
            non_numeric_fields = {str(key): value for key, value in original_payload.items()
                                  if str(key) not in selected}
        else:
            errors.append(f"{candidate.name}: no numeric reward key")
    if selected is not None:
        run_id = os.environ.get("VERIFIER_RUN_ID")
        if not run_id or original_payload.get("run_id") != run_id:
            errors.append("source reward does not belong to this verifier invocation")
            selected = None
        if args.exit_code != 0:
            errors.append("source verifier exited unsuccessfully")
            selected = None
        if selected is not None and selected["reward"] not in (0, 1):
            errors.append("source reward must be zero or one")
            selected = None
    valid_source_reward = selected is not None
    if not valid_source_reward:
        selected = {"reward": 0}
        source = "missing-valid-source-reward"
        errors.append("source verifier did not produce a valid finite reward")
    (root / "reward.json").write_text(
        json.dumps(selected, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    )
    (root / "adapter.json").write_text(
        json.dumps(
            {
                "schema": "cowork-standard-reward-adapter-v1",
                "source": source,
                "source_exit_code": args.exit_code,
                "valid_source_reward": valid_source_reward,
                "parse_errors": errors,
                "source_payloads": source_payloads,
                "non_numeric_fields": non_numeric_fields,
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )
    return 0 if valid_source_reward else 2


if __name__ == "__main__":
    raise SystemExit(main())
