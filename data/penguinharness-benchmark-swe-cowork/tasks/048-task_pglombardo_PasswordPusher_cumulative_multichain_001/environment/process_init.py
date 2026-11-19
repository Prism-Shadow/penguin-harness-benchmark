#!/usr/bin/env python3
"""Run one container command and reap orphaned descendants.

The child may start background tools that outlive an individual terminal exec.
They are reaped when they exit; the supervisor does not impose per-tool cleanup.
"""
import ctypes
import os
import signal
import subprocess
import sys
import time


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv:
        raise SystemExit('usage: process_init.py COMMAND [ARGS...]')
    # Also act as a subreaper when embedded under a launcher rather than PID 1.
    libc = ctypes.CDLL(None, use_errno=True)
    if libc.prctl(36, 1, 0, 0, 0) != 0:
        raise OSError(ctypes.get_errno(), 'cannot enable child subreaper')
    child = subprocess.Popen(argv, start_new_session=True)
    forwarded = None

    def forward(signum, _frame):
        nonlocal forwarded
        forwarded = time.monotonic()
        try:
            os.killpg(child.pid, signum)
        except ProcessLookupError:
            pass

    for signum in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
        signal.signal(signum, forward)
    result = None
    while result is None:
        while True:
            try:
                pid, status = os.waitpid(-1, os.WNOHANG)
            except ChildProcessError:
                pid = 0
            if pid == 0:
                break
            if pid == child.pid:
                result = os.waitstatus_to_exitcode(status)
                child.returncode = result
        if forwarded is not None and time.monotonic() - forwarded >= 2:
            try:
                os.killpg(child.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        if result is None:
            time.sleep(0.01)
    # The primary command is done. Drain descendants before this subreaper exits,
    # including detached sessions adopted from a tool/browser process.
    deadline = time.monotonic() + 2
    while True:
        try:
            pid, _ = os.waitpid(-1, os.WNOHANG)
        except ChildProcessError:
            break
        if pid:
            continue
        descendants = open(f"/proc/self/task/{os.getpid()}/children").read().split()
        signum = signal.SIGKILL if time.monotonic() >= deadline else signal.SIGTERM
        for descendant in descendants:
            try:
                os.kill(int(descendant), signum)
            except ProcessLookupError:
                pass
        time.sleep(0.01)
    return result if result >= 0 else 128 - result


if __name__ == '__main__':
    sys.exit(main())
