#!/usr/bin/env python3
"""Exercise real development tools; this is not a task functionality test."""
import ctypes
import ctypes.util
import json
import os
import shutil
import subprocess
import tempfile
from pyvirtualdisplay import Display

import pytest_cov
import coverage

for binary in ('lsof', 'xauth', 'Xvfb', 'xvfb-run'):
    if not shutil.which(binary):
        raise SystemExit('Missing development binary: ' + binary)
with tempfile.NamedTemporaryFile(prefix='mss-fd-probe-') as handle:
    result = subprocess.run(['lsof', '-Fn', '-p', str(os.getpid())], check=True, text=True, capture_output=True, timeout=15)
    assert 'n' + handle.name in result.stdout.splitlines(), result.stdout
with Display(visible=False, size=(80, 60), color_depth=24, use_xauth=True):
    x11 = ctypes.CDLL(ctypes.util.find_library('X11'))
    x11.XOpenDisplay.argtypes = [ctypes.c_char_p]; x11.XOpenDisplay.restype = ctypes.c_void_p
    x11.XCloseDisplay.argtypes = [ctypes.c_void_p]
    x11.XDefaultScreen.argtypes = [ctypes.c_void_p]; x11.XDefaultScreen.restype = ctypes.c_int
    for name in ('XDisplayWidth', 'XDisplayHeight'):
        getattr(x11, name).argtypes = [ctypes.c_void_p, ctypes.c_int]
        getattr(x11, name).restype = ctypes.c_int
    display = x11.XOpenDisplay(os.environ['DISPLAY'].encode())
    assert display, 'XOpenDisplay failed with a real Xvfb/xauth session'
    try:
        screen = x11.XDefaultScreen(display)
        dimensions = [x11.XDisplayWidth(display, screen), x11.XDisplayHeight(display, screen)]
        assert dimensions == [80, 60], dimensions
    finally:
        x11.XCloseDisplay(display)
print(json.dumps({'lsof_open_descriptor': 'passed', 'xauth_xvfb_real_connection': 'passed', 'screen': dimensions}))

with tempfile.TemporaryDirectory(prefix="mss-pytest-probe-") as directory:
    from pathlib import Path
    probe = Path(directory) / "test_probe.py"
    probe.write_text("def test_runtime():\n    assert 2 + 2 == 4\n")
    subprocess.run(["python3", "-m", "pytest", "--cov=.", "--cov-report=term-missing:skip-covered", "-q", str(probe)], cwd=directory, check=True, timeout=30)
print(json.dumps({"pytest_cov": pytest_cov.__version__, "coverage": coverage.__version__}))
