import errno
import ipaddress
import json
import os
from pathlib import Path
import socket
import struct
import subprocess
import sys
import tempfile
import unittest

from platform_fixture import restore
from production_controls import make_variant
from public_ipc import attribute, field, fields, netlink, one
from session_ipc import Controller, DOWNSTREAM_IPV4_CASES, RouteBroker, address_body, address_value, assert_downstream_selection, attributes, commands, configuration, host_selector, ipv6_listeners, platform, static_address_replacement, tproxy_ports, wait_file


ROOT = Path(__file__).resolve().parent


class KernelProtocolTests(unittest.TestCase):
    def setUp(self):
        self.broker = RouteBroker.__new__(RouteBroker)
        self.broker.configure()
        self.broker.mac = bytes.fromhex("021122334455")

    def test_default_session_dump_matches_bindable_downstreams(self):
        request = netlink(22, 413, struct.pack("=BBBBI", socket.AF_INET, 0, 0, 0, 0), flags=0x301)
        responses = self.broker.respond(request)
        observed = [address_value(response[16:]) for response in responses
                    if struct.unpack_from("=H", response, 4)[0] == 20
                    and struct.unpack_from("=I", response, 20)[0] != 1]
        self.assertEqual(
            {(self.broker.links[index], address) for address, prefix, index in observed},
            set(DOWNSTREAM_IPV4_CASES),
        )
        self.assertEqual({prefix for address, prefix, index in observed}, {24, 27})
        self.assertEqual(len(observed), 2)

    def test_link_name_and_sequence_are_not_constants(self):
        for sequence, name, index in ((819, "down9", 27), (31, "ipsec43", 43)):
            body = struct.pack("=BBHiII", 0, 0, 0, 0, 0, 0) + attribute(3, name.encode() + b"\0")
            response = self.broker.respond(netlink(18, sequence, body, flags=5))
            self.assertEqual(len(response), 2)
            self.assertEqual(struct.unpack_from("=IHHII", response[0])[1:4], (16, 0, sequence))
            self.assertEqual(struct.unpack_from("=i", response[0], 20)[0], index)
            self.assertEqual(struct.unpack_from("=i", response[1], 16)[0], 0)

    def test_loopback_lookup_by_name_index_and_dump(self):
        for index, name, flags in ((0, "lo", 5), (1, None, 5), (0, None, 0x301)):
            with self.subTest(index=index, name=name, flags=flags):
                body = struct.pack("=BBHiII", 0, 0, 0, index, 0, 0)
                if name is not None:
                    body += attribute(3, name.encode() + b"\0")
                replies = self.broker.respond(netlink(18, 617, body, flags=flags))
                links = [reply[16:] for reply in replies if struct.unpack_from("=H", reply, 4)[0] == 16]
                loopback = [link for link in links if one(attributes(link[16:]), 3) == b"lo\0"]
                self.assertEqual(len(loopback), 1)
                self.assertEqual(struct.unpack_from("=H", loopback[0], 2)[0], 772)
                self.assertEqual(struct.unpack_from("=iI", loopback[0], 4), (1, 0x49))
                self.assertEqual(one(attributes(loopback[0][16:]), 1), bytes(6))
                self.assertEqual(len(links), len(self.broker.links) if flags == 0x301 else 1)

    def test_dump_filters_ipv4_ipv6_and_link(self):
        self.broker.addresses[27] = [("198.51.100.17", 27), ("2001:db8::17", 64)]
        for family, address in ((2, "198.51.100.17"), (10, "2001:db8::17")):
            responses = self.broker.respond(netlink(22, 719, struct.pack("=BBBBI", family, 0, 0, 0, 27), flags=0x301))
            self.assertEqual(len(responses), 2)
            self.assertEqual(address_value(responses[0][16:])[0], address)
            self.assertEqual(struct.unpack_from("=H", responses[1], 4)[0], 3)

    def test_link_dump_includes_kernel_mtu_attribute(self):
        request = netlink(18, 911, struct.pack("=BBHiII", 0, 0, 0, 0, 0, 0), flags=0x301)
        responses = self.broker.respond(request)
        observed = {}
        for response in responses:
            if struct.unpack_from("=H", response, 4)[0] != 16:
                continue
            link = attributes(response[32:])
            observed[one(link, 3).rstrip(b"\0").decode()] = struct.unpack("=I", one(link, 4))[0]
        self.assertEqual(observed, {name: 65536 if name == "lo" else 1500
                                    for name in self.broker.links.values()})

    def test_loopback_address_dump(self):
        responses = self.broker.respond(netlink(22, 719, struct.pack("=BBBBI", 0, 0, 0, 0, 1), flags=0x301))
        self.assertEqual({address_value(response[16:]) for response in responses[:-1]},
                         {("127.0.0.1", 8, 1), ("::1", 128, 1)})
        self.assertEqual(struct.unpack_from("=H", responses[-1], 4)[0], 3)

    def test_static_replacement_has_stale_addresses_and_distinct_errno(self):
        command = fields(static_address_replacement(self.broker))
        self.assertEqual(one(command, 1), b"wlan7")
        requested = fields(one(command, 2))
        requested_address = str(ipaddress.ip_address(one(requested, 1)))
        requested_prefix = one(requested, 2)
        self.assertEqual((requested_address, requested_prefix), ("192.0.2.77", 27))
        self.broker.respond(netlink(20, 813, address_body(19, requested_address, requested_prefix), flags=5))
        responses = self.broker.respond(netlink(22, 814, struct.pack("=BBBBI", 0, 0, 0, 0, 19), flags=0x301))
        observed = [address_value(response[16:]) for response in responses[:-1]]
        self.assertIn(("127.0.0.1", 8, 19), observed)
        self.assertIn((requested_address, requested_prefix, 19), observed)
        stale = {(address, prefix, index) for address, prefix, index in observed
                 if not ipaddress.ip_address(address).is_loopback and address != requested_address}
        self.assertEqual(stale, {("192.0.2.7", 24, 19), ("2001:db8:7::1", 64, 19)})
        for address, prefix, index in sorted(stale):
            request = netlink(21, 815, address_body(index, address, prefix), flags=5)
            for error in (errno.ENETUNREACH, errno.EACCES, 0):
                with self.subTest(address=address, error=error):
                    self.broker.address_delete_errno = error
                    response = self.broker.respond(request)[0]
                    self.assertEqual(struct.unpack_from("=i", response, 16)[0], -error)
                    self.assertEqual(response[20:], request)
                    self.assertEqual((address, prefix) in self.broker.addresses[index], bool(error))

    def test_address_mutation_errno_and_state(self):
        body = address_body(19, "198.51.100.41", 27)
        self.broker.respond(netlink(20, 1, body, flags=5))
        self.assertIn(("198.51.100.41", 27), self.broker.addresses[19])
        for error in (errno.ENXIO, errno.EADDRNOTAVAIL, errno.EPERM, 0):
            self.broker.address_delete_errno = error
            response = self.broker.respond(netlink(21, 43, body, flags=5))[0]
            self.assertEqual(struct.unpack_from("=i", response, 16)[0], -error)
            self.assertEqual(response[20:], netlink(21, 43, body, flags=5))
        self.assertNotIn(("198.51.100.41", 27), self.broker.addresses[19])

    def test_missing_link_and_unknown_requests_are_not_success(self):
        body = struct.pack("=BBHiII", 0, 0, 0, 992, 0, 0)
        response = self.broker.respond(netlink(18, 71, body, flags=5))[0]
        self.assertEqual(struct.unpack_from("=i", response, 16)[0], -errno.ENODEV)
        with self.assertRaisesRegex(ValueError, "unsupported"):
            self.broker.respond(netlink(93, 72, body, flags=5))

    def test_attribute_length_validation(self):
        self.assertEqual(attributes(attribute(4, b"abcd")), {4: [b"abcd"]})
        for invalid in (b"\x01", struct.pack("=HH", 3, 4), struct.pack("=HH", 18, 4) + b"a"):
            with self.assertRaises(ValueError):
                attributes(invalid)

    def test_equivalent_host_selectors_and_wrong_subnet(self):
        self.assertTrue(host_selector("192.0.2.17", "192.0.2.17"))
        self.assertTrue(host_selector("192.0.2.17/32", "192.0.2.17"))
        self.assertFalse(host_selector("192.0.2.17/24", "192.0.2.17"))
        self.assertFalse(host_selector("192.0.2.18", "192.0.2.17"))


class DownstreamFixtureTests(unittest.TestCase):
    def test_routing_observations_require_the_current_address(self):
        for _, address in DOWNSTREAM_IPV4_CASES:
            assert_downstream_selection([address, address + "/32"], address)
            for destinations in ([], [None], [address + "/27"], ["192.0.2.17"], [address, "127.0.0.1"]):
                with self.assertRaises(AssertionError):
                    assert_downstream_selection(destinations, address)
        with self.assertRaises(AssertionError):
            assert_downstream_selection([DOWNSTREAM_IPV4_CASES[0][1]], DOWNSTREAM_IPV4_CASES[1][1])

    def test_unexpected_error_keeps_the_production_report(self):
        controller = Controller("unused", {}, ROOT)
        report = field(1, b"AddrNotAvailable") + field(2, b"Cannot assign requested address") + field(3, errno.EADDRNOTAVAIL)
        controller.pending = [(3, fields(field(1, 207) + field(2, report)))]
        with self.assertRaisesRegex(AssertionError, "Cannot assign requested address"):
            controller.take(207, 2, 2)
        self.assertEqual(controller.take(207, 3, 2)[2], [report])


class ProductionBoundaryAssetTests(unittest.TestCase):
    def test_tproxy_ports_use_recorded_listener_address_and_port(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "firewall.json").write_text(json.dumps({
                "ip6tables-restore:mangle:vpnhotspot_v6_protocols": [
                    ["-p", "udp", "-j", "TPROXY", "--on-ip", "::1", "--on-port", "40123"],
                    ["-p", "tcp", "-j", "TPROXY", "--on-ip", "::1", "--on-port", "40124"],
                ]
            }))
            self.assertEqual(tproxy_ports(root, "udp"), [("::1", 40123)])
            self.assertEqual(tproxy_ports(root, "tcp"), [("::1", 40124)])

    def test_configuration_carries_public_nat_and_route_fields(self):
        packet = fields(configuration(
            primary_network=7, primary_routes=("2001:db8::/32",), fallback_network=9,
            primary_upstream_interfaces=("ipsec31",), fallback_upstream_interfaces=("ipsec43",),
            clients=(("02aabbccdd11", "192.0.2.61"),), ipv6_nat_seed="asset-test"))
        self.assertEqual(one(packet, 5), 7)
        self.assertEqual(one(packet, 7), 9)
        self.assertEqual(one(packet, 8), b"ipsec31")
        self.assertEqual(one(packet, 9), b"ipsec43")
        self.assertTrue(one(packet, 10))
        self.assertTrue(one(packet, 11))


class ListenerObservationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.process_id = 5317
        self.process = self.root / str(self.process_id)
        for directory in ("fd", "fdinfo", "net"):
            (self.process / directory).mkdir(parents=True)
        for protocol in ("tcp", "udp"):
            (self.process / "net" / (protocol + "6")).write_text("sl local_address remote_address st\n")

    def add_socket(self, protocol, address, port, inode, descriptor, nonblocking=True, state=None):
        packed = ipaddress.IPv6Address(address).packed
        encoded = "".join(f"{int.from_bytes(packed[offset:offset + 4], sys.byteorder):08X}"
                          for offset in range(0, 16, 4))
        state = state or ("0A" if protocol == "tcp" else "07")
        with (self.process / "net" / (protocol + "6")).open("a") as output:
            output.write(f"0: {encoded}:{port:04X} {'0' * 32}:0000 {state} 0:0 0:0 0 1000 0 {inode}\n")
        if descriptor is not None:
            (self.process / "fd" / str(descriptor)).symlink_to(f"socket:[{inode}]")
            (self.process / "fdinfo" / str(descriptor)).write_text(
                f"pos:\t0\nflags:\t{os.O_RDWR | (os.O_NONBLOCK if nonblocking else 0):o}\n")

    def test_observes_owned_real_endpoints_not_firewall_address_defaults(self):
        for protocol in ("tcp", "udp"):
            for offset, address in enumerate(("::", "::1", "2001:db8:5::19")):
                inode = 7419 + offset + (100 if protocol == "tcp" else 0)
                self.add_socket(protocol, address, 39001 + offset, inode, inode)
            observed = ipv6_listeners(self.process_id, protocol, self.root)
            self.assertEqual({(entry["address"], entry["port"]) for entry in observed},
                             {("::", 39001), ("::1", 39002), ("2001:db8:5::19", 39003)})
            self.assertTrue(all(entry["nonblocking"] for entry in observed))

    def test_excludes_foreign_namespace_sockets_and_non_listening_tcp(self):
        self.add_socket("udp", "::1", 33017, 81001, None)
        self.add_socket("tcp", "::1", 33019, 81002, 9, state="01")
        self.assertEqual(ipv6_listeners(self.process_id, "udp", self.root), [])
        self.assertEqual(ipv6_listeners(self.process_id, "tcp", self.root), [])

    def test_blocking_flag_and_socket_release_are_observed(self):
        self.add_socket("udp", "::", 45119, 88001, 11, nonblocking=False)
        self.assertFalse(ipv6_listeners(self.process_id, "udp", self.root)[0]["nonblocking"])
        (self.process / "fdinfo/11").write_text(f"flags:\t{os.O_RDWR | os.O_NONBLOCK:o}\n")
        self.assertTrue(ipv6_listeners(self.process_id, "udp", self.root)[0]["nonblocking"])
        (self.process / "fd/11").unlink()
        self.assertEqual(ipv6_listeners(self.process_id, "udp", self.root), [])

    def test_missing_procfs_or_unsupported_protocol_is_not_a_pass(self):
        with self.assertRaises(ValueError):
            ipv6_listeners(self.process_id, "raw", self.root)
        (self.process / "net/udp6").unlink()
        with self.assertRaises(FileNotFoundError):
            ipv6_listeners(self.process_id, "udp", self.root)

    def test_closed_descriptor_during_snapshot_cannot_supply_a_listener(self):
        self.add_socket("udp", "::1", 45127, 88003, 13)
        (self.process / "fdinfo/13").unlink()
        self.assertEqual(ipv6_listeners(self.process_id, "udp", self.root), [])


class DownstreamSocketTests(unittest.TestCase):
    def test_ipv6_listener_procfs_roundtrip(self):
        for protocol, socket_type in (("tcp", socket.SOCK_STREAM), ("udp", socket.SOCK_DGRAM)):
            for address in ("::", "::1"):
                with self.subTest(protocol=protocol, address=address):
                    with socket.socket(socket.AF_INET6, socket_type) as listener:
                        listener.bind((address, 0))
                        listener.setblocking(False)
                        if protocol == "tcp":
                            listener.listen(1)
                        port = listener.getsockname()[1]
                        observed = [entry for entry in ipv6_listeners(os.getpid(), protocol) if entry["port"] == port]
                        self.assertEqual(len(observed), 1)
                        self.assertEqual(observed[0]["address"], address)
                        self.assertTrue(observed[0]["nonblocking"])
                        listener.setblocking(True)
                        self.assertFalse(next(entry for entry in ipv6_listeners(os.getpid(), protocol)
                                              if entry["port"] == port)["nonblocking"])
                    self.assertFalse(any(entry["inode"] == observed[0]["inode"]
                                         for entry in ipv6_listeners(os.getpid(), protocol)))

    def test_fixture_addresses_support_real_legacy_dns_binds(self):
        broker = RouteBroker.__new__(RouteBroker)
        broker.configure()
        request = netlink(22, 414, struct.pack("=BBBBI", socket.AF_INET, 0, 0, 0, 0), flags=0x301)
        responses = broker.respond(request)
        downstream_addresses = [address_value(response[16:]) for response in responses
                                if struct.unpack_from("=H", response, 4)[0] == 20]
        self.assertEqual(len(downstream_addresses), 3)
        self.assertEqual({broker.links[index] for address, prefix, index in downstream_addresses},
                         {"lo", "wlan7", "down9"})
        for address, prefix, index in downstream_addresses:
            for socket_type in (socket.SOCK_STREAM, socket.SOCK_DGRAM):
                with self.subTest(downstream=broker.links[index], address=address, socket_type=socket_type):
                    with socket.socket(socket.AF_INET, socket_type) as listener:
                        listener.bind((address, 0))
                        self.assertEqual(listener.getsockname()[0], address)
                        self.assertGreater(listener.getsockname()[1], 0)
                        if socket_type == socket.SOCK_STREAM:
                            listener.listen(1)


class PlatformProtocolTests(unittest.TestCase):
    def test_tproxy_port_discovery_accepts_omitted_optional_address(self):
        with tempfile.TemporaryDirectory() as temporary:
            root, _ = platform(Path(temporary), os.environ)
            for port in (34921, 48107):
                with self.subTest(port=port):
                    for address in (None, "::", "::1"):
                        suffix = "" if address is None else " --on-ip " + address
                        rule = f"-p udp -j TPROXY --on-port {port}{suffix}"
                        self.assertEqual(restore(
                            root, "ip6tables-restore", ["-w", "--noflush"],
                            f"*mangle\n:renamed_chain - [0:0]\n-I renamed_chain {rule}\nCOMMIT\n",
                        )[0], 0)
                        self.assertEqual(tproxy_ports(root, "udp"), [(address, port)])
                        self.assertEqual(tproxy_ports(root, "tcp"), [])

    def test_firewall_state_head_insertion_and_repeated_cleanup(self):
        with tempfile.TemporaryDirectory() as temporary:
            root, _ = platform(Path(temporary), os.environ)
            arguments = ["-w", "--noflush"]
            self.assertEqual(restore(root, "iptables-restore", arguments,
                                    "*filter\n-N custom\n-I custom -j REJECT\n-I custom -j RETURN\nCOMMIT\n")[0], 0)
            state = json.loads((root / "firewall.json").read_text())
            self.assertEqual(state["iptables-restore:filter:custom"], [["-j", "RETURN"], ["-j", "REJECT"]])
            deletion = "*filter\n-D custom -j RETURN\nCOMMIT\n"
            self.assertEqual(restore(root, "iptables-restore", arguments, deletion)[0], 0)
            self.assertEqual(restore(root, "iptables-restore", arguments, deletion)[0], 1)
            self.assertEqual(restore(root, "iptables-restore", arguments, "*filter\n:custom - [0:0]\n-X custom\nCOMMIT\n")[0], 0)
            self.assertEqual(json.loads((root / "firewall.json").read_text())["iptables-restore:filter:custom"], [])

    def test_failed_create_and_failed_postcondition_are_independent(self):
        with tempfile.TemporaryDirectory() as temporary:
            root, _ = platform(Path(temporary), os.environ, chain_create_fails=True)
            arguments = ["-w", "--noflush"]
            self.assertEqual(restore(root, "iptables-restore", arguments, "*nat\n-N custom\nCOMMIT\n")[0], 1)
            self.assertEqual(restore(root, "iptables-restore", arguments, "*nat\n-L custom -n\nCOMMIT\n")[0], 0)
            (root / "config.json").write_text(json.dumps({"chain_list_fails": True}))
            self.assertEqual(restore(root, "iptables-restore", arguments, "*nat\n-L custom -n\nCOMMIT\n")[0], 1)
            with self.assertRaisesRegex(ValueError, "unsupported"):
                restore(root, "iptables-restore", arguments, "*nat\n-UNKNOWN custom\nCOMMIT\n")

    def test_real_subprocess_split_output_gate_and_failure(self):
        with tempfile.TemporaryDirectory() as temporary:
            root, environment = platform(Path(temporary), os.environ,
                                         scans=[{"gated": True, "chunks": ["abc", "\ndef", "\n"], "status": 7}])
            with subprocess.Popen([str(root / "bin/dumpsys"), "ipsec"], env=environment,
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE) as process:
                wait_file(root / "scan-0.started")
                self.assertIsNone(process.poll())
                (root / "scan-0.release").touch()
                stdout, stderr = process.communicate(timeout=5)
                self.assertEqual((process.returncode, stdout, stderr), (7, b"abc\ndef\n", b""))
            self.assertEqual([entry["phase"] for entry in commands(root)], ["start", "finish"])
            invalid = subprocess.run([str(root / "bin/dumpsys"), "ipsec"], env=environment, capture_output=True)
            self.assertEqual(invalid.returncode, 125)
            self.assertIn("unexpected_scan", commands(root)[-1])


class ProcessInterpositionTests(unittest.TestCase):
    def test_libc_launches_reach_the_fixture_without_system_mounts(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            library = directory / "platform.so"
            subprocess.run(["cc", "-std=c11", "-Wall", "-Wextra", "-Werror", "-shared", "-fPIC",
                            str(ROOT / "environment/netlink_broker.c"), str(ROOT / "environment/platform_broker.c"),
                            "-ldl", "-o", str(library)], check=True)
            source = directory / "launch.c"
            source.write_text('''#define _GNU_SOURCE
#include <spawn.h>
#include <string.h>
#include <sys/wait.h>
#include <unistd.h>
extern char **environ;
int main(int count, char **values) {
    if (count != 2) return 90;
    char *arguments[] = {"/system/bin/dumpsys", "ipsec", 0};
    if (!strcmp(values[1], "execve")) return execve(arguments[0], arguments, environ);
    if (!strcmp(values[1], "execvp")) return execvp(arguments[0], arguments);
    pid_t process;
    int result = !strcmp(values[1], "spawn")
        ? posix_spawn(&process, arguments[0], 0, 0, arguments, environ)
        : posix_spawnp(&process, arguments[0], 0, 0, arguments, environ);
    if (result) return 91;
    int status;
    if (waitpid(process, &status, 0) < 0 || !WIFEXITED(status)) return 92;
    return WEXITSTATUS(status);
}
''')
            executable = directory / "launch"
            subprocess.run(["cc", "-Wall", "-Wextra", "-Werror", str(source), "-o", str(executable)], check=True)
            for mode in ("execve", "execvp", "spawn", "spawnp"):
                root, environment = platform(directory / mode, os.environ, scans=[{"chunks": ["external-input-" + mode]}])
                result = subprocess.run([str(executable), mode], env=dict(environment, LD_PRELOAD=str(library)), capture_output=True)
                self.assertEqual((result.returncode, result.stdout, result.stderr), (0, ("external-input-" + mode).encode(), b""))
                self.assertEqual(commands(root)[0]["program"], "dumpsys")


class ControlAssetTests(unittest.TestCase):
    def test_relocation_changes_only_module_locations(self):
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary)
            modules = ("neighbour", "routing", "control", "downstream", "ipsec", "socket", "upstream")
            (source / "main.rs").write_text("\n".join(f"mod {module};" for module in (*modules, "nat66")))
            for module in modules:
                (source / f"{module}.rs").write_text(f"fn {module}() {{}}\n")
            (source / "routing").mkdir()
            (source / "routing/desired.rs").write_text("fn rules() {}\n")
            (source / "nat66/icmp").mkdir(parents=True)
            (source / "nat66/mod.rs").write_text("mod icmp;\n")
            (source / "nat66/icmp/mod.rs").write_text("fn quoted() {}\n")
            (source / "shared").mkdir()
            shared = ("ipsec", "model", "icmp_nat")
            (source / "shared/mod.rs").write_text("\n".join(f"pub mod {module};" for module in shared))
            for module in shared:
                (source / f"shared/{module}.rs").write_text(f"pub fn {module}() {{}}\n")
            make_variant(source, "relocated")
            for module in modules:
                self.assertFalse((source / f"{module}.rs").exists())
                self.assertEqual((source / f"platform_io/{module}.rs").read_text(), f"fn {module}() {{}}\n")
            self.assertEqual((source / "platform_io/routing/desired.rs").read_text(), "fn rules() {}\n")
            self.assertEqual((source / "platform_io/nat66/icmp/mod.rs").read_text(), "fn quoted() {}\n")
            for module in shared:
                self.assertEqual((source / f"shared/policy/{module}.rs").read_text(), f"pub fn {module}() {{}}\n")


if __name__ == "__main__":
    unittest.main()
