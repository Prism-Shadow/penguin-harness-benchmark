"""Deterministic Android subprocess I/O; no daemon decisions or Rust APIs."""
import fcntl
import json
import os
from pathlib import Path
import shlex
import sys
import time


class UnexpectedScan(Exception):
    pass


def append(root, entry):
    entry = dict(entry, monotonic_seconds=time.monotonic())
    with (root / "commands.jsonl").open("a") as output:
        fcntl.flock(output, fcntl.LOCK_EX)
        output.write(json.dumps(entry, sort_keys=True) + "\n")


def restore(root, name, arguments, content, *, counters=None):
    if arguments != ["-w", "--noflush"]:
        raise ValueError(f"unsupported restore arguments: {arguments}")
    config = json.loads((root / "config.json").read_text())
    with (root / "firewall.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        state_path = root / "firewall.json"
        state = json.loads(state_path.read_text()) if state_path.exists() else {}
        status, output, table = 0, [], None
        for line in content.splitlines():
            if line.startswith("*"):
                table = line[1:]
                continue
            if not line or line == "COMMIT":
                continue
            if line.startswith(":") and table is not None:
                state[f"{name}:{table}:{line.split()[0][1:]}"] = []
                continue
            tokens = shlex.split(line)
            if tokens[:3] == ["-nvx", "-L", "vpnhotspot_stats"]:
                counters = counters if counters is not None else os.environ.get("VPNHOTSPOT_COUNTER_FIXTURE")
                output.append(Path(counters).read_text() if counters else "")
                continue
            if table is None or len(tokens) < 2:
                raise ValueError(f"unsupported restore input: {line}")
            operation, chain, *rule = tokens
            key = f"{name}:{table}:{chain}"
            rules = state.setdefault(key, [])
            if operation == "-N":
                status = int(config.get("chain_create_fails", False))
            elif operation == "-L":
                status = int(config.get("chain_list_fails", False))
                output.append("Chain " + chain + "\n")
            elif operation in ("-I", "-A"):
                if rule and rule[0].isdigit():
                    position = int(rule.pop(0)) - 1
                else:
                    position = 0 if operation == "-I" else len(rules)
                rules.insert(position, rule)
            elif operation in ("-D", "-C"):
                status = int(rule not in rules)
                if not status and operation == "-D":
                    rules.remove(rule)
            elif operation in ("-F", "-X"):
                rules.clear()
            else:
                raise ValueError(f"unsupported firewall operation: {operation}")
            if status:
                break
        state_path.write_text(json.dumps(state, sort_keys=True))
    append(root, {"program": name, "argv": arguments, "stdin": content, "status": status})
    return status, "".join(output)


def dumpsys(root, arguments):
    if arguments != ["ipsec"]:
        raise ValueError(f"unsupported dumpsys arguments: {arguments}")
    with (root / "scans.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        count_path = root / "scan-count"
        index = int(count_path.read_text()) if count_path.exists() else 0
        plans = json.loads((root / "config.json").read_text()).get("scans", [])
        if index >= len(plans):
            raise UnexpectedScan(f"unplanned IPsec scan {index}")
        plan = plans[index]
        count_path.write_text(str(index + 1))
        append(root, {"program": "dumpsys", "phase": "start", "index": index, "pid": os.getpid()})
        (root / f"scan-{index}.started").touch()
    deadline = time.monotonic() + 20
    while plan.get("gated") and not (root / f"scan-{index}.release").exists():
        if time.monotonic() > deadline:
            raise ValueError(f"IPsec fixture release timed out: {index}")
        time.sleep(0.01)
    for chunk in plan.get("chunks", []):
        sys.stdout.write(chunk)
        sys.stdout.flush()
        if plan.get("chunk_delay"):
            time.sleep(plan["chunk_delay"])
    append(root, {"program": "dumpsys", "phase": "finish", "index": index})
    (root / f"scan-{index}.finished").touch()
    return plan.get("status", 0)


def main():
    root = Path(os.environ["VPNHOTSPOT_PLATFORM_FIXTURE"])
    name, *arguments = sys.argv[1:]
    try:
        if name == "dumpsys":
            return dumpsys(root, arguments)
        if name not in ("iptables-restore", "ip6tables-restore"):
            raise ValueError(f"unknown platform program: {name}")
        status, output = restore(root, name, arguments, sys.stdin.read())
        sys.stdout.write(output)
        return status
    except UnexpectedScan as error:
        append(root, {"unexpected_scan": str(error)})
        return 125
    except Exception as error:
        append(root, {"fixture_error": f"{type(error).__name__}: {error}"})
        return 125


if __name__ == "__main__":
    raise SystemExit(main())
