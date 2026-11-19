#!/usr/bin/env python3
"""Bound a command without leaving a detached timer process behind.

Supports the timeout options used by the terminal runtime and ordinary development
commands. The timer belongs to the waiting parent; normal completion cancels it.
"""
import argparse
import math
import os
import re
import signal
import subprocess
import sys
import time


def duration(value):
    match = re.fullmatch(r'(\d+(?:\.\d*)?|\.\d+)([smhd]?)', value)
    if not match:
        raise argparse.ArgumentTypeError('invalid nonnegative duration: ' + value)
    seconds = float(match[1]) * {'': 1, 's': 1, 'm': 60, 'h': 3600, 'd': 86400}[match[2]]
    if not math.isfinite(seconds):
        raise argparse.ArgumentTypeError('duration is not finite')
    return seconds


def signal_number(value):
    try:
        number = int(value) if value.isdigit() else int(getattr(signal, 'SIG' + value.upper().removeprefix('SIG')))
        if number not in signal.valid_signals():
            raise ValueError(value)
        return number
    except (AttributeError, ValueError):
        raise argparse.ArgumentTypeError('invalid signal: ' + value)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, usage='timeout [OPTION] DURATION COMMAND [ARG]...')
    parser.add_argument('-s', '--signal', type=signal_number, default=signal.SIGTERM)
    parser.add_argument('-k', '--kill-after', type=duration)
    parser.add_argument('--preserve-status', action='store_true')
    parser.add_argument('--foreground', action='store_true')
    parser.add_argument('-v', '--verbose', action='store_true')
    parser.add_argument('--version', action='version', version='cowork timeout 1 (parent-owned timer)')
    parser.add_argument('duration', type=duration)
    parser.add_argument('command', nargs=argparse.REMAINDER)
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return 0 if exc.code == 0 else 125
    if not args.command:
        parser.print_usage(sys.stderr)
        return 125
    try:
        child = subprocess.Popen(args.command, start_new_session=not args.foreground)
    except FileNotFoundError as exc:
        print('timeout: ' + str(exc), file=sys.stderr)
        return 127
    except OSError as exc:
        print('timeout: ' + str(exc), file=sys.stderr)
        return 126

    def send(signum):
        if args.verbose:
            print('timeout: sending signal ' + str(signum), file=sys.stderr)
        try:
            (os.kill if args.foreground else os.killpg)(child.pid, signum)
        except ProcessLookupError:
            pass

    previous = {}
    for signum in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP, signal.SIGQUIT):
        previous[signum] = signal.signal(signum, lambda sig, _frame: send(sig))
    timed_out = forced = False
    try:
        try:
            child.wait(timeout=args.duration or None)
        except subprocess.TimeoutExpired:
            timed_out = True
            signalled_at = time.monotonic()
            send(args.signal)
            try:
                child.wait(timeout=args.kill_after or None)
            except subprocess.TimeoutExpired:
                forced = True
                send(signal.SIGKILL)
                child.wait()
            # A shell can exit on TERM while one of its children ignores it.
            # Keep the kill-after promise for the same command process group.
            if args.kill_after and not args.foreground and not forced:
                while True:
                    try:
                        os.killpg(child.pid, 0)
                    except ProcessLookupError:
                        break
                    if time.monotonic() - signalled_at >= args.kill_after:
                        send(signal.SIGKILL)
                        break
                    time.sleep(0.01)
    finally:
        for signum, handler in previous.items():
            signal.signal(signum, handler)
    status = child.returncode if child.returncode >= 0 else 128 - child.returncode
    if args.preserve_status or not timed_out:
        return status
    return 137 if forced or args.signal == signal.SIGKILL else 124


if __name__ == '__main__':
    sys.exit(main())
