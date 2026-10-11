#!/usr/bin/env python3
"""How many Docker networks this host can still create from the daemon's default address pools.

    python3 tools/gdpevo/protocol/pools.py [--need N] [--stale] [--json]
        [--pools <base/len:size>,...] [--daemon-json /etc/docker/daemon.json]

Every Harbor trial creates a Compose network of its own (its egress sidecar joins it), which
Docker carves out of the default address pools. The stock pools are 172.17.0.0/16 to
172.31.0.0/16 (fifteen /16s) and 192.168.0.0/16 in /20s (sixteen): 31 networks for the whole
host, every user and every evaluation on it included. `default-address-pools` in the daemon's
configuration replaces them (read when the file is readable); `--pools 10.10.0.0/16:24,...`
overrides both.

A pool subnet is used when it overlaps the subnet of an existing network (`docker network
inspect`), an on-link host route (`/proc/net/route`: the host's own LANs as well as Docker's
bridges) or a nameserver of /etc/resolv.conf; Docker skips the last two as well. The first line
printed is `<used>/<total> used, <free> free`.

- `--need N` exits 1 when fewer than N subnets are free.
- `--stale` lists the pool networks without a running container, oldest first: name, subnet,
  creation date, and whether the name is a Harbor trial's (`<trial>__env_default`, left behind
  by an interrupted trial). A stopped stack's network looks the same, so the list is for a human
  to decide on: this script never removes anything.
- `--json` prints one object instead: `total`, `used`, `free`, `free_subnets`, `used_by`,
  `stale`, `pools`, `pools_from` and a one-line `summary`.

Standard library and the `docker` CLI only. Exit 2 when Docker cannot be read.
"""

from __future__ import annotations

import argparse
import ipaddress
import json
import re
import socket
import struct
import subprocess
import sys

# Docker's built-in local-scope pools (moby's ipamutils): 172.17.0.0/16 through 172.31.0.0/16 as
# /16s, then 192.168.0.0/16 as /20s.
STOCK_POOLS = [
    ("172.17.0.0/16", 16),
    ("172.18.0.0/15", 16),
    ("172.20.0.0/14", 16),
    ("172.24.0.0/13", 16),
    ("192.168.0.0/16", 20),
]
HARBOR_TRIAL_NETWORK = re.compile(r"__env_default$")
LIST_LIMIT = 8


def fail(message: str) -> None:
    print(f"pools.py: {message}", file=sys.stderr)
    sys.exit(2)


def docker(*args: str) -> str:
    try:
        done = subprocess.run(["docker", *args], capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.TimeoutExpired) as error:
        fail(f"docker {args[0]} failed: {error}")
    if done.returncode != 0:
        fail(f"docker {' '.join(args[:2])} failed: {done.stderr.strip()}")
    return done.stdout


def parse_pools(entries: list[tuple[str, object]], origin: str) -> list[tuple[ipaddress.IPv4Network, int]]:
    pools = []
    for base, size in entries:
        try:
            network, size = ipaddress.ip_network(str(base), strict=True), int(size)
        except (ValueError, TypeError):
            fail(f"{origin}: not a pool: base {base!r}, size {size!r}")
        if network.version != 4 or not network.prefixlen <= size <= 32:
            fail(f"{origin}: not an IPv4 pool: {base}:{size}")
        pools.append((network, size))
    return pools


def daemon_pools(path: str) -> list[tuple[str, object]] | None:
    try:
        with open(path, encoding="utf-8") as f:
            config = json.load(f)
    except (OSError, ValueError):
        return None
    entries = config.get("default-address-pools") if isinstance(config, dict) else None
    if not isinstance(entries, list) or not entries:
        return None
    return [(e.get("base"), e.get("size")) for e in entries if isinstance(e, dict)]


def networks() -> list[dict]:
    ids = docker("network", "ls", "--quiet").split()
    found = []
    for net in json.loads(docker("network", "inspect", *ids)) if ids else []:
        subnets = []
        for config in (net.get("IPAM") or {}).get("Config") or []:
            try:
                subnet = ipaddress.ip_network(str(config.get("Subnet") or ""), strict=False)
            except ValueError:
                continue
            if subnet.version == 4:
                subnets.append(subnet)
        found.append({
            "name": net.get("Name", ""),
            "subnets": subnets,
            "containers": len(net.get("Containers") or {}),
            "created": str(net.get("Created") or "")[:19].replace("T", " "),
        })
    return found


def host_routes() -> list[tuple[ipaddress.IPv4Network, str]]:
    """On-link IPv4 routes (no gateway) other than the default route, with their interface."""
    routes = []
    try:
        with open("/proc/net/route", encoding="ascii") as f:
            lines = f.read().splitlines()[1:]
    except OSError:
        return routes
    for line in lines:
        fields = line.split()
        if len(fields) < 8 or int(fields[2], 16) != 0 or int(fields[1], 16) == 0:
            continue
        address = socket.inet_ntoa(struct.pack("<L", int(fields[1], 16)))
        netmask = socket.inet_ntoa(struct.pack("<L", int(fields[7], 16)))
        try:
            routes.append((ipaddress.ip_network(f"{address}/{netmask}", strict=False), fields[0]))
        except ValueError:
            continue
    return routes


def nameservers() -> list[ipaddress.IPv4Network]:
    found = []
    try:
        with open("/etc/resolv.conf", encoding="utf-8") as f:
            for line in f:
                fields = line.split()
                if len(fields) < 2 or fields[0] != "nameserver":
                    continue
                try:
                    address = ipaddress.ip_address(fields[1])
                except ValueError:
                    continue
                if address.version == 4 and not address.is_loopback:
                    found.append(ipaddress.ip_network(f"{address}/32"))
    except OSError:
        pass
    return found


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--need", type=int, help="exit 1 when fewer than N subnets are free")
    parser.add_argument("--stale", action="store_true", help="list pool networks without a running container")
    parser.add_argument("--json", action="store_true", help="print one JSON object")
    parser.add_argument("--pools", help="the daemon's default pools, as <base/len:size>,...")
    parser.add_argument("--daemon-json", default="/etc/docker/daemon.json", help="the daemon's configuration file")
    args = parser.parse_args()

    if args.pools:
        entries = [item.strip().partition(":")[::2] for item in args.pools.split(",") if item.strip()]
        pools, origin = parse_pools(entries, "--pools"), "--pools"
    else:
        configured = daemon_pools(args.daemon_json)
        origin = args.daemon_json if configured else "stock"
        pools = parse_pools(configured or STOCK_POOLS, origin)

    nets = networks()
    reserved: list[tuple[ipaddress.IPv4Network, str]] = []
    for net in nets:
        reserved += [(subnet, f"network {net['name']}") for subnet in net["subnets"]]
    reserved += [(route, f"host route {route} dev {iface}") for route, iface in host_routes()]
    reserved += [(server, f"nameserver {server.network_address}") for server in nameservers()]

    used_by: dict[str, str] = {}
    free: list[str] = []
    for network, size in pools:
        for candidate in network.subnets(new_prefix=size):
            owner = next((why for subnet, why in reserved if candidate.overlaps(subnet)), None)
            if owner is None:
                free.append(str(candidate))
            else:
                used_by[str(candidate)] = owner
    total = len(used_by) + len(free)

    stale = sorted(
        (
            {"name": net["name"], "subnets": [str(s) for s in net["subnets"]], "created": net["created"],
             "harbor_trial": bool(HARBOR_TRIAL_NETWORK.search(net["name"]))}
            for net in nets
            if net["containers"] == 0 and any(s.overlaps(p) for s in net["subnets"] for p, _ in pools)
        ),
        key=lambda n: n["created"],
    )
    blocked = sorted(f"{subnet} ({why})" for subnet, why in used_by.items() if not why.startswith("network "))
    summary = (
        f"{len(used_by)}/{total} used, {len(free)} free"
        + (f" ({', '.join(free[:LIST_LIMIT])}{', …' if len(free) > LIST_LIMIT else ''})" if free else "")
        + ("; stock pools" if origin == "stock" else f"; pools from {origin}")
        + (f"; not usable for the host: {'; '.join(blocked)}" if blocked else "")
    )
    if args.json:
        print(json.dumps({
            "total": total,
            "used": len(used_by),
            "free": len(free),
            "free_subnets": free,
            "used_by": used_by,
            "stale": stale,
            "pools": [{"base": str(b), "size": s} for b, s in pools],
            "pools_from": origin,
            "summary": summary,
        }, indent=2))
    else:
        print(summary)
        print(f"pools: {', '.join(f'{b}:{s}' for b, s in pools)} ({origin})")
        if args.stale:
            print(f"pool networks without a running container: {len(stale)} (this script removes nothing)")
            for n in stale:
                print(f"  {n['name']}  {', '.join(n['subnets'])}  created {n['created'][:10]}"
                      + ("  Harbor trial network" if n["harbor_trial"] else ""))
    if args.need is not None and len(free) < args.need:
        if not args.json:
            print(f"need {args.need} free, have {len(free)}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
