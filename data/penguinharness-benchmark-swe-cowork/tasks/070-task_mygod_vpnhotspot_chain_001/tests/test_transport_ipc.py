import copy
from contextlib import contextmanager
import errno
import ipaddress
import json
import os
from pathlib import Path
import stat
import struct
import subprocess
import tempfile
import unittest
from unittest.mock import Mock, patch

from public_ipc import attribute, field, netlink, one
from session_ipc import attributes
from transport_ipc import (CLIENT, MAC, QueueBroker, decoded_echo_quote, echo_packet, error_reports,
                           icmp_policies, kernel_release, policy_check, queued_packet, sockaddr, wait_for)
from public_ipc import fields


ROOT = Path(__file__).resolve().parent


class TransportFixtureTests(unittest.TestCase):
    def policies(self, downstream="wlan7"):
        incoming = [["-i", downstream, "-p", "icmpv6", "--icmpv6-type", kind, "-j", "RETURN"]
                    for kind in ("133", "135", "136")]
        incoming += [["-i", downstream, "-p", "tcp", "-j", "TPROXY", "--on-port", "39017"]]
        outgoing = [["-o", downstream, "-p", "icmpv6", "--icmpv6-type", "134", "-m", "mark",
                     "--mark", "0x00030063/0x0003ffff", "-j", "ACCEPT"],
                    ["-o", downstream, "-p", "icmpv6", "--icmpv6-type", "134", "-j", "REJECT"]]
        return {"ip6tables-restore:mangle:vpnhotspot_v6_tproxy": incoming,
                "ip6tables-restore:filter:vpnhotspot_v6_output": outgoing,
                "ip6tables-restore:mangle:PREROUTING": [["-j", "vpnhotspot_v6_tproxy"]],
                "ip6tables-restore:filter:OUTPUT": [["-j", "vpnhotspot_v6_output"]]}

    def check_policy(self, state, downstream="wlan7", enabled=True):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "firewall.json").write_text(json.dumps(state))
            policy_check(root, downstream, enabled)

    def test_policy_positive_relocation_and_unrelated_typed_rule(self):
        for downstream in ("wlan7", "down9"):
            state = self.policies(downstream)
            state["ip6tables-restore:mangle:vpnhotspot_v6_tproxy"].append(
                ["-i", downstream, "-p", "icmpv6", "--icmpv6-type", "2", "-j", "RETURN"])
            self.check_policy(state, downstream)

    def test_policy_rejects_each_missing_policy(self):
        for key, rules in self.policies().items():
            if "vpnhotspot_v6_" not in key:
                continue
            for index in range(3 if "mangle" in key else 2):
                state = self.policies()
                state[key].pop(index)
                with self.subTest(key=key, index=index), self.assertRaises(AssertionError):
                    self.check_policy(state)

    def test_policy_rejects_reversed_and_late_precedence(self):
        for key in self.policies():
            if "vpnhotspot_v6_" not in key:
                continue
            state = self.policies()
            state[key].reverse()
            with self.subTest(key=key), self.assertRaises(AssertionError):
                self.check_policy(state)

    def test_policy_rejects_wrong_family_interface_mark_and_extra_returns(self):
        original = self.policies()
        variants = []
        state = {key.replace("ip6tables", "iptables"): rules for key, rules in original.items()}
        variants.append(state)
        variants.append(self.policies("hardcoded0"))
        state = copy.deepcopy(original)
        rule = state["ip6tables-restore:filter:vpnhotspot_v6_output"][0]
        position = rule.index("--mark")
        del rule[position:position + 2]
        variants.append(state)
        for mark in ("0x30062/0x3ffff", "0x30063/0xffffffff"):
            state = copy.deepcopy(original)
            rule = state["ip6tables-restore:filter:vpnhotspot_v6_output"][0]
            rule[rule.index("--mark") + 1] = mark
            variants.append(state)
        for kind in ("134", "137"):
            state = copy.deepcopy(original)
            state["ip6tables-restore:mangle:vpnhotspot_v6_tproxy"].insert(0, ["--icmpv6-type", kind, "-j", "RETURN"])
            variants.append(state)
        for index, state in enumerate(variants):
            with self.subTest(index=index), self.assertRaises(AssertionError):
                self.check_policy(state)

    def test_policy_disabled_requires_real_removal(self):
        self.check_policy({}, enabled=False)
        with self.assertRaises(AssertionError):
            self.check_policy(self.policies(), enabled=False)

    def test_policy_rejects_disconnected_chains(self):
        for key in ("ip6tables-restore:mangle:PREROUTING", "ip6tables-restore:filter:OUTPUT"):
            state = self.policies()
            state.pop(key)
            with self.assertRaises(AssertionError):
                self.check_policy(state)

    def test_nfqueue_packet_uses_real_linux_layout(self):
        packet = echo_packet("ff02::1", 327, 59)
        encoded = queued_packet(941, packet, 27, queue=31007)
        size, kind, flags, _, _ = struct.unpack_from("=IHHII", encoded)
        self.assertEqual((size, kind, flags), (len(encoded), 0x300, 0))
        self.assertEqual(struct.unpack_from("!BBH", encoded, 16), (10, 0, 31007))
        parsed = attributes(encoded[20:])
        self.assertEqual(one(parsed, 1), struct.pack("!IHB", 941, 0x86dd, 0))
        self.assertEqual(one(parsed, 5), struct.pack("!I", 27))
        self.assertEqual(one(parsed, 9)[4:10], bytes.fromhex(MAC))
        self.assertEqual(one(parsed, 10), packet)
        self.assertEqual(packet[8:24], ipaddress.IPv6Address(CLIENT).packed)
        self.assertEqual(struct.unpack_from("!HH", packet, 44), (327, 59))

    def test_nfqueue_ack_verdict_and_unknown_message(self):
        broker = QueueBroker.__new__(QueueBroker)
        broker.records = []
        request = netlink(0x302, 79, struct.pack("!BBH", 10, 0, 31007) + attribute(1, bytes([1, 0, 0, 0])), flags=5)
        reply = broker.respond(request)
        self.assertEqual(reply, [netlink(2, 79, struct.pack("=i", 0) + request, flags=0)])
        self.assertEqual(broker.queue, 31007)
        self.assertTrue(broker.bound)
        for identifier, verdict in ((17, 1), (19, 0)):
            body = struct.pack("!BBH", 10, 0, 31007) + attribute(2, struct.pack("!II", verdict, identifier))
            broker.records.append({"type": 0x301, "body_hex": body.hex()})
            self.assertEqual(broker.verdict(identifier), [verdict])
        self.assertIsNone(broker.verdict(21))
        with self.assertRaises(ValueError):
            broker.respond(netlink(0x399, 79, bytes(4)))

    def test_raw_sockaddr_layout_and_structured_error(self):
        address = sockaddr("2001:db8:1::17")
        self.assertEqual(len(address), 28)
        self.assertEqual(struct.unpack_from("=H", address)[0], 10)
        self.assertEqual(address[8:24], ipaddress.IPv6Address("2001:db8:1::17").packed)
        report = field(1, b"relay-context") + field(3, errno.EACCES)
        reports = error_reports([(4, {2: [report]}), (1, {})])
        self.assertEqual(one(reports[0], 3), errno.EACCES)

    def test_wait_does_not_invent_an_observation(self):
        with self.assertRaises(AssertionError):
            wait_for(lambda: None, "not observed", timeout=0.001)

    def test_quote_observer_accepts_preserved_extensions_not_private_layout(self):
        direct = echo_packet("2001:db8:1::9", 327, 59)
        extended = echo_packet("2001:db8:1::9", 327, 59, 60, bytes([58, 0]) + bytes(6))
        self.assertEqual(decoded_echo_quote(direct), decoded_echo_quote(extended))
        initial = echo_packet("2001:db8:1::9", 327, 59, 44, bytes([58, 0, 0, 1]) + bytes(4))
        self.assertEqual(decoded_echo_quote(direct), decoded_echo_quote(initial))
        noninitial = echo_packet("2001:db8:1::9", 327, 59, 44, bytes([58, 0, 0, 8]) + bytes(4))
        for invalid in (extended[:43], noninitial, bytes(48)):
            with self.assertRaises(AssertionError):
                decoded_echo_quote(invalid)

    def test_policy_and_release_scenarios_commit_a_client_before_nat_observation(self):
        class ObservedStart(Exception):
            pass

        class StartObserver:
            def start(observer, call_id, config):
                decoded = fields(config)
                self.assertEqual(call_id, 301)
                self.assertEqual(len(decoded.get(10, [])), 1, "NAT setup short-circuits without a client")
                self.assertIn(11, decoded)
                raise ObservedStart()

        @contextmanager
        def fixture(*arguments, **keywords):
            yield StartObserver(), None, None, None, None

        for scenario in (icmp_policies, kernel_release):
            with self.subTest(scenario=scenario.__name__), patch("transport_ipc.session", fixture), self.assertRaises(ObservedStart):
                scenario(None, {}, Path("unused"))

    def test_policy_scenario_observes_each_lifecycle_transition(self):
        controllers = []
        observations = []

        @contextmanager
        def fixture(binary, environment, directory):
            controller = Mock()
            controller.active = False
            controller.start.side_effect = lambda call_id, config: setattr(controller, "active", 11 in fields(config))
            controller.replace.side_effect = lambda call_id, session_id, config: setattr(controller, "active", 11 in fields(config))
            controller.clean.side_effect = lambda call_id: setattr(controller, "active", False)
            controllers.append(controller)
            yield controller, controller, None, Mock(bound="VPNHOTSPOT_ICMP_UNAVAILABLE" not in environment), None

        def observe(controller, downstream, enabled=True):
            self.assertEqual(controller.active, enabled)
            observations.append((downstream, enabled))

        with patch("transport_ipc.session", fixture), patch("transport_ipc.policy_check", observe), patch(
                "transport_ipc.transport_records", return_value=[{"event": "icmp-capability"}]):
            icmp_policies(None, {}, Path("unused"))
        self.assertEqual(len(controllers), 8)
        self.assertEqual(observations, [(downstream, enabled) for downstream in ("wlan7", "down9")
                                       for capability in (True, False)
                                       for enabled in (True, False, True, False, False, True, False)])
        for controller in controllers:
            controller.clean.assert_called_once()

    def test_c_abi_without_privileged_sockets(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            library, executable = root / "transport.so", root / "smoke"
            for command in (["cc", "-std=c11", "-Wall", "-Wextra", "-Werror", "-shared", "-fPIC", "-o", str(library), str(ROOT / "environment/transport_broker.c"), "-ldl"],
                            ["cc", "-std=c11", "-Wall", "-Wextra", "-Werror", "-o", str(executable), str(ROOT / "environment/transport_abi_smoke.c"), "-ldl"]):
                subprocess.run(command, check=True, capture_output=True, text=True)
            environment = dict(os.environ, LD_PRELOAD=str(library), VPNHOTSPOT_TRANSPORT_FIXTURE=str(root), VPNHOTSPOT_KERNEL_RELEASE="4.17.")
            trace = root / "transport.jsonl"
            for existing_private_log in (False, True):
                with self.subTest(existing_private_log=existing_private_log):
                    if existing_private_log:
                        trace.chmod(0o600)
                    subprocess.run([str(executable)], check=True, env=environment, umask=0o077,
                                   capture_output=True, text=True)
                    self.assertEqual(stat.S_IMODE(trace.stat().st_mode), 0o644)
                    records = [json.loads(line) for line in trace.read_text().splitlines()]
                    self.assertEqual([(entry["event"], entry["network"]) for entry in records],
                                     [("network", 0x1234567800000063)] * (2 if existing_private_log else 1))


if __name__ == "__main__":
    unittest.main()
