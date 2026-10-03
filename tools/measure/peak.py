#!/usr/bin/env python3
"""Exit 0 when a peak pricing window starts or is open within the horizon, else 1.

    python3 tools/measure/peak.py [--within 3h] [--tz Asia/Shanghai]
        [--windows "Mon-Fri 09:00-12:00,14:00-18:00"] [--now <ISO time>]

The defaults are DeepSeek's peak schedule as PenguinHarness prices it (v0.2.13): weekdays
09:00-12:00 and 14:00-18:00 Beijing time at the peak rate, twice the off-peak one, and
off-peak otherwise. Public holidays are not modelled: the product prices a holiday weekday
at peak, and so does this check. `--windows` takes groups separated by ";", each a day list
(`Mon-Fri`, `Sat,Sun`) and comma-separated `HH:MM-HH:MM` ranges.

run_attempts.sh asks before every job whether a peak window falls within the next 3 hours
(the longest job); guard.sh asks every interval about the next 5 minutes. Prints one line
saying which window it found, or that there is none; standard library only.
"""

from __future__ import annotations

import argparse
import datetime as dt
import re
import sys
from zoneinfo import ZoneInfo

DAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
DEFAULT_WINDOWS = "Mon-Fri 09:00-12:00,14:00-18:00"
_DURATION = re.compile(r"^([0-9]+)([smh]?)$")
_RANGE = re.compile(r"^([0-9]{1,2}):([0-9]{2})-([0-9]{1,2}):([0-9]{2})$")


def duration(text: str) -> dt.timedelta:
    match = _DURATION.match(text.strip())
    if not match:
        raise argparse.ArgumentTypeError(f"bad duration {text!r} (examples: 3h, 5m, 90s)")
    return dt.timedelta(seconds=int(match.group(1)) * {"": 1, "s": 1, "m": 60, "h": 3600}[match.group(2)])


def _days(spec: str) -> set[int]:
    days: set[int] = set()
    for part in spec.lower().split(","):
        ends = part.split("-")
        if not all(end[:3] in DAYS for end in ends) or len(ends) > 2:
            raise argparse.ArgumentTypeError(f"bad day list {spec!r} (examples: Mon-Fri, Sat,Sun)")
        first, last = DAYS.index(ends[0][:3]), DAYS.index(ends[-1][:3])
        days.update(range(first, last + 1) if first <= last else [*range(first, 7), *range(0, last + 1)])
    return days


def windows(text: str) -> list[tuple[set[int], dt.time, dt.time]]:
    """[(weekdays, start, end)] from "Mon-Fri 09:00-12:00,14:00-18:00; Sat 10:00-11:00"."""
    result = []
    for group in filter(None, (g.strip() for g in text.split(";"))):
        try:
            day_spec, ranges = group.split(None, 1)
        except ValueError:
            raise argparse.ArgumentTypeError(f"bad window group {group!r}") from None
        days = _days(day_spec)
        for span in ranges.replace(" ", "").split(","):
            match = _RANGE.match(span)
            if not match:
                raise argparse.ArgumentTypeError(f"bad time range {span!r} (example: 09:00-12:00)")
            h1, m1, h2, m2 = (int(g) for g in match.groups())
            if (h1, m1) >= (h2, m2) or h2 > 24 or (h2 == 24 and m2):
                raise argparse.ArgumentTypeError(f"bad time range {span!r}")
            end = dt.time(23, 59, 59, 999999) if h2 == 24 else dt.time(h2, m2)
            result.append((days, dt.time(h1, m1), end))
    if not result:
        raise argparse.ArgumentTypeError("no peak windows given")
    return result


def first_peak(now: dt.datetime, within: dt.timedelta, spec: list, tz: ZoneInfo) -> tuple[dt.datetime, dt.datetime] | None:
    """The first window [start, end) that overlaps [now, now + within], in tz."""
    horizon = now + within
    day = now.astimezone(tz).date() - dt.timedelta(days=1)
    found = []
    while day <= horizon.astimezone(tz).date():
        for days, start, end in spec:
            if day.weekday() not in days:
                continue
            begin = dt.datetime.combine(day, start, tzinfo=tz)
            finish = dt.datetime.combine(day, end, tzinfo=tz)
            if begin <= horizon and finish > now:
                found.append((begin, finish))
        day += dt.timedelta(days=1)
    return min(found) if found else None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--within", type=duration, default=dt.timedelta(hours=3), help="horizon (default 3h)")
    parser.add_argument("--tz", default="Asia/Shanghai", help="IANA time zone of the windows (default Asia/Shanghai)")
    parser.add_argument("--windows", type=windows, default=windows(DEFAULT_WINDOWS), help=f'default "{DEFAULT_WINDOWS}"')
    parser.add_argument("--now", help="evaluate at this ISO 8601 time instead of the current time (a time without an offset is in --tz)")
    args = parser.parse_args()

    try:
        tz = ZoneInfo(args.tz)
    except Exception as exc:  # ZoneInfoNotFoundError, or a malformed key
        parser.error(f"unknown time zone {args.tz!r}: {exc}")
    if args.now:
        now = dt.datetime.fromisoformat(args.now)
        now = now if now.tzinfo else now.replace(tzinfo=tz)
    else:
        now = dt.datetime.now(dt.timezone.utc)
    hit = first_peak(now, args.within, args.windows, tz)
    span = f"{int(args.within.total_seconds())} s"
    if hit is None:
        print(f"no peak window within {span} of {now.astimezone(tz).isoformat(timespec='minutes')}")
        return 1
    begin, finish = hit
    print(
        f"peak window {begin.strftime('%a %Y-%m-%d %H:%M')}-{finish.strftime('%H:%M')} {args.tz} "
        f"overlaps the {span} from {now.astimezone(tz).isoformat(timespec='minutes')}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
