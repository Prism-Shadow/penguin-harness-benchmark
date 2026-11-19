"""Real socket regressions for total RPC bounds; production controls run separately."""
from contextlib import contextmanager
from concurrent.futures import ThreadPoolExecutor
import socket
import struct
import threading
import time
import unittest

from public_ipc import field
from session_ipc import Controller


@contextmanager
def connected():
    controller = Controller('unused', {}, '.')
    # socketpair avoids spawning any daemon in these harness-only checks.
    left, right = socket.socketpair()
    with left, right:
        controller.socket = left
        yield controller, right


def reply(call_id, data=b''):
    packet = field(1, field(1, call_id) + field(2, data))
    return struct.pack('!I', len(packet)) + packet


class RpcDeadlineTests(unittest.TestCase):
    def test_fragmented_reply_within_budget_is_accepted(self):
        with connected() as (controller, peer), ThreadPoolExecutor(max_workers=1) as pool:
            packet = reply(71)
            def send():
                peer.sendall(packet[:2])
                time.sleep(0.02)
                peer.sendall(packet[2:])
            sender = pool.submit(send)
            try:
                self.assertEqual(controller.take(71, 1, 2, timeout=2)[1], [71])
            finally:
                sender.result(timeout=2)

    def test_missing_acknowledgement_is_bounded(self):
        with connected() as (controller, peer):
            with self.assertRaises(TimeoutError):
                controller.take(71, 1, 2, timeout=0.05)

    def test_partial_frame_cannot_renew_total_deadline(self):
        with connected() as (controller, peer), ThreadPoolExecutor(max_workers=1) as pool:
            # Keep the socket readable at every recv. A per-recv timeout would
            # incorrectly accept this deliberately slow, otherwise valid frame.
            packet = reply(71, b'x' * 200)
            stop = threading.Event()
            def send():
                peer.sendall(packet[:5])
                for byte in packet[5:]:
                    if stop.wait(0.01):
                        return
                    peer.sendall(bytes([byte]))
            sender = pool.submit(send)
            try:
                with self.assertRaises(TimeoutError):
                    controller.take(71, 1, 2, timeout=0.1)
            finally:
                stop.set()
                sender.result(timeout=2)

    def test_unrelated_complete_frames_cannot_renew_total_deadline(self):
        with connected() as (controller, peer), ThreadPoolExecutor(max_workers=1) as pool:
            stop = threading.Event()
            def send():
                while not stop.wait(0.01):
                    peer.sendall(reply(93))
            sender = pool.submit(send)
            try:
                with self.assertRaises((TimeoutError, AssertionError)):
                    controller.take(71, 1, 2, timeout=0.1)
                self.assertTrue(controller.pending)
            finally:
                stop.set()
                sender.result(timeout=2)
