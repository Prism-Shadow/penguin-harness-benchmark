#!/usr/bin/env python3
from __future__ import annotations

import argparse
import codecs
import os
import re
import selectors
import signal
import subprocess
import sys
import time
from pathlib import Path


VERSIONS = ("1.56.0", "1.58.0")
DOWNLOAD_TIMEOUT_SECONDS = 900
CFT_INSTALL_TIMEOUT_SECONDS = 4200
CFT_INSTALL_BUDGET_SECONDS = 5100
CHECK_TIMEOUT_SECONDS = 120
CFT_CDN = "https://cdn.playwright.dev/chrome-for-testing-public/"
CFT_ORIGIN = "https://storage.googleapis.com/chrome-for-testing-public/"
CHROMIUM_HOST = "PLAYWRIGHT_CHROMIUM_DOWNLOAD_HOST"


def command(version: str, arguments: list[str], *, offline: bool) -> list[str]:
    if version not in VERSIONS:
        raise ValueError(f"unreviewed Playwright version: {version}")
    return ["npm", "exec", *(["--offline"] if offline else []), "--yes",
            f"--package=playwright@{version}", "--", "playwright", *arguments]


def run(arguments: list[str], *, timeout: float, capture: bool = False,
        environment: dict[str, str] | None = None,
        progress_timeout: float | None = None) -> str:
    if progress_timeout is not None and capture:
        raise ValueError("download progress must be streamed, not captured")
    print("RUN", arguments, "deadline_seconds", timeout, flush=True)
    with subprocess.Popen(arguments, start_new_session=True, text=progress_timeout is None,
                          env=environment, stdout=subprocess.PIPE if capture or progress_timeout is not None else None) as process:
        try:
            if progress_timeout is None:
                output, _ = process.communicate(timeout=timeout)
            else:
                stream_download(process, timeout=timeout, progress_timeout=progress_timeout)
                output = ""
        except subprocess.TimeoutExpired:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.communicate()
            print("FAIL Playwright process-group deadline exceeded", flush=True)
            raise
        if process.returncode:
            raise subprocess.CalledProcessError(process.returncode, arguments, output=output)
        return output or ""


def stream_download(process: subprocess.Popen, *, timeout: float, progress_timeout: float) -> None:
    started = time.monotonic()
    last_progress = started
    decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")
    pending = ""
    artifact = None
    percentages: dict[str, int] = {}
    print("DOWNLOAD no_forward_progress_seconds", progress_timeout, flush=True)
    with selectors.DefaultSelector() as selector:
        selector.register(process.stdout, selectors.EVENT_READ)
        while True:
            now = time.monotonic()
            wall_remaining = started + timeout - now
            idle_remaining = last_progress + progress_timeout - now
            remaining = min(wall_remaining, idle_remaining)
            if remaining <= 0:
                reason = "absolute deadline" if wall_remaining <= 0 else "no forward download progress"
                print("FAIL Playwright", reason, flush=True)
                raise subprocess.TimeoutExpired(process.args, timeout if wall_remaining <= 0 else progress_timeout)
            if not selector.get_map():
                process.wait(timeout=remaining)
                return
            for key, _ in selector.select(timeout=remaining):
                chunk = os.read(key.fd, 8192)
                if not chunk:
                    selector.unregister(key.fileobj)
                    continue
                text = decoder.decode(chunk)
                sys.stdout.write(text)
                sys.stdout.flush()
                lines = re.split(r"[\r\n]", pending + text)
                pending = lines.pop()[-4096:]
                for line in lines:
                    download = re.fullmatch(r"Downloading (.+) from https://\S+", line.strip())
                    if download:
                        artifact = download.group(1)
                    progress = re.fullmatch(r"\|[^|]*\|\s*(\d{1,3})% of \d+(?:\.\d+)? [A-Za-z]+", line.strip())
                    if progress and artifact:
                        percent = int(progress.group(1))
                        if percentages.get(artifact, -1) < percent <= 100:
                            percentages[artifact] = percent
                            last_progress = time.monotonic()


def download_urls(plan: str) -> list[str]:
    urls = re.findall(r"^\s*Download url:\s*(\S+)\s*$", plan, flags=re.MULTILINE)
    if not urls or any(not url.startswith("https://") for url in urls):
        raise ValueError("Playwright dry-run did not disclose any HTTPS download URLs")
    return urls


def origin_environment(version: str) -> dict[str, str]:
    if version != "1.58.0":
        raise ValueError("Chrome for Testing origin routing is only reviewed for Playwright 1.58.0")
    for variable in ("PLAYWRIGHT_DOWNLOAD_HOST", CHROMIUM_HOST):
        if os.environ.get(variable):
            raise ValueError(f"unexpected inherited Playwright download override: {variable}")
    arguments = command(version, ["install", "--dry-run", "chromium"], offline=False)
    original = download_urls(run(arguments, timeout=CHECK_TIMEOUT_SECONDS, capture=True))
    cft_urls = [url for url in original if url.startswith(CFT_CDN)]
    if len(cft_urls) != 2 or len(set(cft_urls)) != 2:
        raise ValueError("expected distinct full Chromium and headless-shell CFT downloads")
    artifacts = []
    for url in cft_urls:
        artifact = re.fullmatch(re.escape(CFT_CDN) + r"([0-9]+(?:\.[0-9]+){3})/linux64/(chrome(?:-headless-shell)?)-linux64\.zip", url)
        if artifact is None:
            raise ValueError(f"unreviewed Chrome for Testing artifact: {url}")
        artifacts.append(artifact.groups())
    if len({artifact[0] for artifact in artifacts}) != 1 or {artifact[1] for artifact in artifacts} != {"chrome", "chrome-headless-shell"}:
        raise ValueError("full Chromium and headless shell must share the native browser version")
    expected = [url.replace(CFT_CDN, CFT_ORIGIN, 1) if url.startswith(CFT_CDN) else url
                for url in original]
    environment = os.environ.copy()
    environment[CHROMIUM_HOST] = CFT_ORIGIN.rstrip("/")
    routed = download_urls(run(arguments, timeout=CHECK_TIMEOUT_SECONDS, capture=True,
                               environment=environment))
    if routed != expected:
        raise ValueError(f"Playwright origin override changed artifact identity: expected {expected}, got {routed}")
    for source, destination in zip(original, routed):
        print("VERIFIED native download route", source, "->", destination, flush=True)
    return environment


def install(version: str) -> None:
    arguments = command(version, ["install", "chromium"], offline=False)
    environment = origin_environment(version) if version == "1.58.0" else None
    deadline = time.monotonic() + CFT_INSTALL_BUDGET_SECONDS if version == "1.58.0" else None
    for attempt in range(1, 3):
        route = "official CFT origin" if environment is not None else "upstream CDN"
        print(f"Playwright {version}: install attempt {attempt}/2 via {route}", flush=True)
        try:
            if deadline is None:
                run(arguments, timeout=DOWNLOAD_TIMEOUT_SECONDS, environment=environment)
            else:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise subprocess.TimeoutExpired(arguments, CFT_INSTALL_BUDGET_SECONDS)
                run(arguments, timeout=min(CFT_INSTALL_TIMEOUT_SECONDS, remaining),
                    progress_timeout=DOWNLOAD_TIMEOUT_SECONDS, environment=environment)
            return
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError) as error:
            if attempt == 2 or (environment is None and not isinstance(error, subprocess.TimeoutExpired)):
                raise
            if environment is not None:
                environment = None
                print("Official origin failed; using the original pinned upstream CDN after 5 seconds", flush=True)
            else:
                print("Retrying the identical pinned download after 5 seconds", flush=True)
            time.sleep(5)


def check(version: str, work: Path) -> None:
    actual = run(command(version, ["--version"], offline=True),
                 timeout=CHECK_TIMEOUT_SECONDS, capture=True).strip()
    if actual != f"Version {version}":
        raise ValueError(f"Playwright version drift: expected {version}, got {actual!r}")
    work.mkdir(parents=True, exist_ok=True)
    screenshot = work / f"chromium-{version}.png"
    if screenshot.exists():
        raise ValueError(f"offline smoke requires fresh output: {screenshot}")
    run(command(version, ["screenshot", "--browser=chromium",
                          "data:text/html,<title>offline browser smoke</title>", str(screenshot)], offline=True),
        timeout=CHECK_TIMEOUT_SECONDS)
    if not screenshot.is_file() or screenshot.stat().st_size == 0:
        raise ValueError("Chromium did not produce the offline smoke screenshot")
    print(f"PASS Playwright {version}: exact offline CLI and real headless Chromium launch", flush=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("install", "check"))
    parser.add_argument("version", choices=VERSIONS)
    parser.add_argument("--work", type=Path, default=Path("/opt/browser-preparation"))
    arguments = parser.parse_args()
    try:
        if arguments.mode == "install":
            install(arguments.version)
        else:
            check(arguments.version, arguments.work)
    except subprocess.TimeoutExpired:
        return 124
    except subprocess.CalledProcessError as error:
        return error.returncode if error.returncode > 0 else 128 - error.returncode
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
