#!/usr/bin/env python3
"""Record the DeepSeek account balance before and after a job, and the difference.

    python3 tools/balance.py read --key-file FILE --out jobs/balance-<job>-before.json
    python3 tools/balance.py read --key-file FILE --out jobs/balance-<job>-after.json
    python3 tools/balance.py delta jobs/balance-<job>-before.json jobs/balance-<job>-after.json

`read` calls GET <base-url>/user/balance with the key read from FILE (never from the
command line or the environment) and writes the response without the key:
{"fetched_at", "endpoint", "is_available", "balance_infos": [{"currency",
"total_balance", "granted_balance", "topped_up_balance"}]}. `delta` prints, per currency,
{"currency", "amount"} with amount = after total - before total as a decimal string
(negative = spent), the shape results/README.md uses for `balance_delta`.

The key is never printed: error messages have it replaced with [REDACTED]. Needs only
Python >= 3.11 (urllib); honours the usual https_proxy environment variables.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
import urllib.error
import urllib.request
from decimal import Decimal, InvalidOperation
from pathlib import Path


def _redact(text: str, key: str) -> str:
    return text.replace(key, "[REDACTED]") if key else text


def read_balance(key_file: Path, base_url: str, timeout: float) -> dict:
    key = key_file.expanduser().read_text(encoding="utf-8").strip()
    if not key:
        raise SystemExit(f"balance.py: {key_file} is empty")
    endpoint = base_url.rstrip("/") + "/user/balance"
    request = urllib.request.Request(
        endpoint, headers={"Authorization": f"Bearer {key}", "Accept": "application/json"}
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:500]
        raise SystemExit(_redact(f"balance.py: HTTP {exc.code} from {endpoint}: {detail}", key)) from None
    except (urllib.error.URLError, TimeoutError, ValueError) as exc:
        raise SystemExit(_redact(f"balance.py: cannot read {endpoint}: {exc}", key)) from None
    record = {
        "fetched_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "endpoint": endpoint,
        "is_available": body.get("is_available"),
        "balance_infos": [
            {k: info.get(k) for k in ("currency", "total_balance", "granted_balance", "topped_up_balance")}
            for info in body.get("balance_infos") or []
            if isinstance(info, dict)
        ],
    }
    text = json.dumps(record)
    if key in text:  # the API never echoes the key; refuse to write it if it ever did
        raise SystemExit("balance.py: the response contained the key; nothing written")
    return record


def _totals(record: dict) -> dict[str, Decimal]:
    totals = {}
    for info in record.get("balance_infos") or []:
        try:
            totals[str(info.get("currency"))] = Decimal(str(info.get("total_balance")))
        except InvalidOperation:
            continue
    return totals


def delta(before: dict, after: dict) -> list[dict]:
    old, new = _totals(before), _totals(after)
    return [
        {"currency": currency, "amount": str(new[currency] - old[currency])}
        for currency in sorted(set(old) & set(new))
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    read = sub.add_parser("read", help="read the balance and write it as JSON")
    read.add_argument("--key-file", type=Path, required=True, help="file holding the DeepSeek API key")
    read.add_argument("--out", type=Path, help="write here (default: stdout)")
    read.add_argument("--base-url", default="https://api.deepseek.com")
    read.add_argument("--timeout", type=float, default=30.0)
    diff = sub.add_parser("delta", help="difference between two balance files")
    diff.add_argument("before", type=Path)
    diff.add_argument("after", type=Path)
    args = parser.parse_args()

    if args.command == "read":
        text = json.dumps(read_balance(args.key_file, args.base_url, args.timeout), indent=2) + "\n"
        if args.out:
            args.out.parent.mkdir(parents=True, exist_ok=True)
            args.out.write_text(text, encoding="utf-8")
        else:
            sys.stdout.write(text)
        return 0
    before = json.loads(args.before.read_text(encoding="utf-8"))
    after = json.loads(args.after.read_text(encoding="utf-8"))
    print(json.dumps(delta(before, after)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
