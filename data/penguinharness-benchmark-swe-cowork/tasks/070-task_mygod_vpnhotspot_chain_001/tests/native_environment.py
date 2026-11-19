import ctypes
from functools import lru_cache
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile


ANDROID_SYMBOLS = (
    "android_get_device_api_level", "android_setsocknetwork", "android_res_nsend",
    "android_res_nresult", "android_res_cancel",
)
LOG_SYMBOLS = ("__android_log_print", "__android_log_write")


class NativeEnvironmentError(OSError):
    pass


def validate_native_stubs(directory: Path) -> None:
    for filename, symbols in (("libandroid.so", ANDROID_SYMBOLS), ("liblog.so", LOG_SYMBOLS)):
        library = ctypes.CDLL(str(directory / filename))
        for symbol in symbols:
            if not hasattr(library, symbol):
                raise NativeEnvironmentError(f"{directory / filename}: missing Android ABI symbol {symbol}")


@lru_cache(maxsize=None)
def build_native_stubs(source: Path, destination: Path) -> Path:
    source = source / "android_stubs.c"
    destination.mkdir(parents=True, exist_ok=True)
    output = Path(tempfile.mkdtemp(prefix="android-abi-", dir=destination))
    commands = []
    for filename in ("libandroid.so", "liblog.so"):
        command = ["cc", "-shared", "-fPIC", "-Wall", "-Wextra", "-Werror", "-Wl,-z,defs",
                   str(source), "-o", str(output / filename)]
        result = subprocess.run(command, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        commands.append({"command": command, "exit_code": result.returncode, "output": result.stdout})
        if result.returncode:
            raise NativeEnvironmentError(f"native stub build failed: {result.stdout}")
    validate_native_stubs(output)
    (output / "build.json").write_text(json.dumps({
        "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(), "commands": commands,
        "symbols": list(ANDROID_SYMBOLS + LOG_SYMBOLS),
    }, indent=2) + "\n")
    return output
