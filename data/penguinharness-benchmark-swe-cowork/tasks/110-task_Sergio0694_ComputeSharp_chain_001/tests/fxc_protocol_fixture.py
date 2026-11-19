import json
import os
import struct
import sys


def number():
    return struct.unpack('<I', sys.stdin.buffer.read(4))[0]


def blob():
    return sys.stdin.buffer.read(number())


def string():
    return blob().decode() if number() else None


def send_number(value):
    sys.stdout.buffer.write(struct.pack('<I', value))


def send_blob(value):
    send_number(len(value))
    sys.stdout.buffer.write(value)


def send_string(value):
    send_number(1)
    send_blob(value.encode())


operation = number()
source = blob()
status, diagnostic = 0, b''
request = {'operation': operation, 'source': source.decode()}
if operation == 1:
    request['name'] = string()
    request['macros'] = [[string(), string()] for _ in range(number())]
    request['entry'], request['target'] = string(), string()
    request['flags'], request['effects'], request['include_mode'] = number(), number(), number()
    if source == b'abort':
        raise SystemExit(3)
    if source == b'oversized':
        for value in (4, 0, 64 * 1024 * 1024 + 1):
            send_number(value)
        raise SystemExit(0)
    if source == b'negative':
        status, diagnostic = 0x80004005, b'compiler diagnostic'
    if source == b'include':
        request['includes'] = []
        for identifier, parent, name in ((0, 0xffffffff, 'root.hlsli'), (1, 0, 'nested.hlsli')):
            for value in (5, identifier, 0, parent):
                send_number(value)
            send_string(name)
            sys.stdout.buffer.flush()
            include_status, contents = number(), blob()
            request['includes'].append([include_status, contents.decode()])
        for identifier in (1, 0):
            send_number(6)
            send_number(identifier)
            sys.stdout.buffer.flush()
            request.setdefault('closed', []).append(number())
elif operation == 2:
    request['part'], request['flags'], request['extra'] = number(), number(), blob().decode()
elif operation == 3:
    request['flags'], request['comments'] = number(), string()
else:
    os._exit(4)
send_number(4)
send_number(status)
send_blob(json.dumps(request, sort_keys=True).encode() if not status else b'')
send_blob(diagnostic)
sys.stdout.buffer.flush()
