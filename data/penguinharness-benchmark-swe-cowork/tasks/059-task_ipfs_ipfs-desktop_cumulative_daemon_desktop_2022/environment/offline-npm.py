#!/usr/bin/env python3
import functools
import http.server
import os
import subprocess
import sys
import threading
from pathlib import Path


def run(arguments, mirror=Path('/opt/go-ipfs-dist')):
    if not (mirror / 'go-ipfs/versions').is_file():
        raise FileNotFoundError(f'offline Kubo metadata is missing: {mirror}')
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(mirror))
    with http.server.ThreadingHTTPServer(('127.0.0.1', 0), handler) as server:
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        environment = {**os.environ, 'GO_IPFS_DIST_URL': f'http://127.0.0.1:{server.server_port}',
                       'npm_config_jobs': '2', 'MAKEFLAGS': '-j2',
                       'NO_PROXY': '127.0.0.1,localhost', 'no_proxy': '127.0.0.1,localhost'}
        try:
            return subprocess.run(arguments, env=environment, check=False).returncode
        finally:
            server.shutdown()
            worker.join()


if __name__ == '__main__':
    raise SystemExit(run(['npm', *sys.argv[1:]]))
