"""Run the firewall I/O model once per daemon, retaining actual child processes.

Python interpreter startup used to dominate every iptables invocation (dozens
per session) on a loaded container host. Only transport changes: the same model
receives every argv/stdin, maintains the same state/logs, and returns the same
stdout/exit status. dumpsys remains a separately gated streaming subprocess.
"""
from pathlib import Path
import secrets
import socket
import struct
import threading

from platform_fixture import append, restore


class FirewallBroker:
    def __init__(self, root):
        self.root = Path(root)
        self.name = 'vpn-firewall-' + secrets.token_hex(12)
        self.socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.socket.bind('\0' + self.name)
        self.socket.listen(64)
        self.socket.settimeout(0.1)
        self.stopped = threading.Event()
        self.thread = threading.Thread(target=self.run, daemon=True)

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *error):
        self.stopped.set()
        self.thread.join(timeout=12)
        self.socket.close()
        if self.thread.is_alive():
            raise RuntimeError('firewall fixture did not stop')

    def run(self):
        while not self.stopped.is_set():
            try:
                connection, _ = self.socket.accept()
            except socket.timeout:
                continue
            with connection:
                connection.settimeout(10)
                try:
                    def read(length):
                        value = bytearray()
                        while len(value) < length:
                            chunk = connection.recv(length - len(value))
                            if not chunk:
                                raise ValueError('truncated firewall request')
                            value.extend(chunk)
                        return bytes(value)

                    def number():
                        return struct.unpack('!I', read(4))[0]

                    def text():
                        length = number()
                        if length > 1048576:
                            raise ValueError('oversized firewall argument')
                        return read(length).decode()

                    count = number()
                    if not 1 <= count <= 64:
                        raise ValueError('invalid firewall argument count')
                    program, *arguments = [text() for _ in range(count)]
                    counters = text()
                    content = bytearray()
                    while True:
                        length = number()
                        if length > 65536 or len(content) + length > 16 * 1048576:
                            raise ValueError('oversized firewall stdin')
                        if not length:
                            break
                        content.extend(read(length))
                    program = Path(program).name
                    if program not in ('iptables-restore', 'ip6tables-restore'):
                        raise ValueError('unknown firewall executable')
                    status, output = restore(self.root, program, arguments,
                                             content.decode(), counters=counters)
                except Exception as error:
                    append(self.root, {'fixture_error': f'{type(error).__name__}: {error}'})
                    status, output = 125, ''
                payload = output.encode()
                try:
                    connection.sendall(struct.pack('!II', status, len(payload)) + payload)
                except OSError as error:
                    append(self.root, {'fixture_error': f'firewall response: {error}'})
