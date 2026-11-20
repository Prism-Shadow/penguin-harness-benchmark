from __future__ import annotations

import ctypes
import platform
import sys
from collections import Counter, namedtuple
from types import SimpleNamespace


def number(value):
    return getattr(value, "value", value)


class Function:
    def __init__(self, name, owner):
        self.__name__ = name
        self.owner = owner
        self.argtypes = None
        self.restype = None
        self.errcheck = None

    def __call__(self, *args):
        self.owner.calls[self.__name__] += 1
        self.owner.events.append((self.__name__, args))
        result = self.owner.invoke(self.__name__, args)
        if self.errcheck is not None:
            checked = self.errcheck(result, self, args)
            if checked is not args:
                return checked
        return result


class Library:
    def __init__(self, owner):
        self.owner = owner
        self.functions = {}

    def __getattr__(self, name):
        return self.functions.setdefault(name, Function(name, self.owner))


class WindowsNative:
    def __init__(self, monkeypatch):
        self.calls = Counter()
        self.events = []
        self.fail = {}
        self.error_code = 0
        self.storage = {}
        self.desktop_dcs = set()
        self.memory_dcs = set()
        self.selected = {}
        self.pending = None
        self.frame = 0
        self.next_handle = 100
        self.user32 = Library(self)
        self.gdi32 = Library(self)
        self.shcore = Library(self)
        self.kernel32 = Library(self)
        monkeypatch.setattr(ctypes, "WINFUNCTYPE", ctypes.CFUNCTYPE, raising=False)
        monkeypatch.setattr(ctypes, "WinDLL", self.load, raising=False)
        monkeypatch.setattr(ctypes, "windll", SimpleNamespace(user32=self.user32, gdi32=self.gdi32, shcore=self.shcore, kernel32=self.kernel32), raising=False)
        monkeypatch.setattr(ctypes, "get_last_error", lambda: self.error_code, raising=False)
        monkeypatch.setattr(ctypes, "set_last_error", self.set_error, raising=False)
        monkeypatch.setattr(ctypes, "WinError", self.win_error, raising=False)
        version = namedtuple("WindowsVersion", "major minor build platform service_pack")(10, 0, 0, 2, "")
        monkeypatch.setattr(sys, "getwindowsversion", lambda: version, raising=False)
        monkeypatch.setattr(platform, "system", lambda: "Windows")

    def set_error(self, value):
        previous, self.error_code = self.error_code, value
        return previous

    def win_error(self, code=None):
        error = OSError(f"synthetic native error {code}")
        error.winerror = self.error_code if code is None else code
        error.strerror = str(error)
        return error

    def load(self, name, **kwargs):
        return getattr(self, str(name).lower().removesuffix(".dll"))

    def invoke(self, name, args):
        if name in self.fail:
            return self.fail[name]
        if name == "GetLastError":
            return self.error_code
        if name == "SetLastError":
            return self.set_error(number(args[0]))
        if name in {"GetWindowDC", "GetDC", "CreateCompatibleDC"}:
            self.next_handle += 1
            handles = self.memory_dcs if name == "CreateCompatibleDC" else self.desktop_dcs
            handles.add(self.next_handle)
            return self.next_handle
        if name == "CreateDIBSection":
            bitmap_info = getattr(args[1], "_obj", args[1])
            header = getattr(bitmap_info, "contents", bitmap_info).bmiHeader
            size = abs(number(header.biWidth) * number(header.biHeight)) * 4
            self.next_handle += 1
            storage = (ctypes.c_ubyte * size)()
            self.storage[self.next_handle] = storage
            ctypes.cast(args[3], ctypes.POINTER(ctypes.c_void_p))[0] = ctypes.addressof(storage)
            return self.next_handle
        if name == "SelectObject":
            self.selected[number(args[0])] = number(args[1])
        elif name == "BitBlt":
            self.frame += 1
            self.pending = self.selected[number(args[0])]
        elif name == "GdiFlush":
            if self.pending is not None:
                storage = self.storage[self.pending]
                pixel = (self.frame, 7, 19, 255)
                storage[:] = pixel * (len(storage) // 4)
                self.pending = None
        elif name == "DeleteObject":
            del self.storage[number(args[0])]
        elif name == "DeleteDC":
            self.memory_dcs.remove(number(args[0]))
        elif name == "ReleaseDC":
            self.desktop_dcs.remove(number(args[1]))
        elif name == "GetSystemMetrics":
            return 32 if number(args[0]) in (0, 1, 78, 79) else 0
        return 1

    def capture(self, backend="gdi"):
        import mss

        return mss.mss(backend=backend)
