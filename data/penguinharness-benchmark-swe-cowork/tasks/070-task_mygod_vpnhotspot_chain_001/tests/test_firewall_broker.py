"""Assert subprocess transport preserves the complete firewall fixture boundary."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from firewall_broker import FirewallBroker
from session_ipc import platform, commands


class FirewallTransportTests(unittest.TestCase):
    def test_new_transport_matches_original_python_process(self):
        inputs = [
            ('iptables-restore', ['-w', '--noflush'], '*filter\n-N custom\n-I custom -j REJECT\n-I custom -j RETURN\nCOMMIT\n'),
            ('ip6tables-restore', ['-w', '--noflush'], '*mangle\n:other - [0:0]\n-I other -p udp -j TPROXY --on-port 49152\nCOMMIT\n'),
            ('iptables-restore', ['-w', '--noflush'], '*filter\n-C custom -j RETURN\nCOMMIT\n'),
            ('iptables-restore', ['-w', '--noflush'], '*filter\n-D custom -j RETURN\nCOMMIT\n'),
            ('iptables-restore', ['-w', '--noflush'], '*filter\n-D custom -j RETURN\nCOMMIT\n'),
            ('iptables-restore', ['-w', '--noflush'], '*filter\n-nvx -L vpnhotspot_stats\nCOMMIT\n'),
            ('iptables-restore', ['-w', '--noflush'], '*filter\n:custom - [0:0]\n-X custom\nCOMMIT\n'),
            ('iptables-restore', ['-w', '--noflush'], '*nat\n-N custom\nCOMMIT\n'),
            ('iptables-restore', ['-w', '--noflush'], '*nat\n-L custom -n\nCOMMIT\n'),
            ('iptables-restore', ['invalid'], '*nat\n-N custom\nCOMMIT\n'),
            ('iptables-restore', ['-w', '--noflush'], '*nat\n-UNKNOWN custom\nCOMMIT\n'),
        ]
        fixture = Path(__file__).with_name('platform_fixture.py')
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            counter = base / 'counters'
            counter.write_text('17 201 ACCEPT all -- wlan7 * 192.0.2.9 0.0.0.0/0\n')
            env = dict(os.environ, VPNHOTSPOT_COUNTER_FIXTURE=str(counter))
            roots = [platform(base / name, env, chain_create_fails=True, chain_list_fails=True)
                     for name in ('python', 'native')]
            results = []
            for mode, (root, environment) in enumerate(roots):
                with FirewallBroker(root) as broker:
                    environment = dict(environment, VPNHOTSPOT_FIREWALL_BROKER=broker.name)
                    actual = []
                    for name, args, content in inputs:
                        command = ([sys.executable, '-I', '-S', '-B', str(fixture), name]
                                   if mode == 0 else [str(root / 'bin' / name)])
                        result = subprocess.run(command + args, input=content, text=True,
                                                env=environment, capture_output=True, timeout=5)
                        actual.append((result.returncode, result.stdout, result.stderr))
                    results.append((actual, json.loads((root / 'firewall.json').read_text()),
                                    [{k: v for k, v in row.items() if k != 'monotonic_seconds'}
                                     for row in commands(root)]))
                self.assertFalse(broker.thread.is_alive())
            self.assertEqual(results[0], results[1])
            self.assertEqual([entry[0] for entry in results[1][0]], [1, 0, 1, 1, 1, 0, 0, 1, 1, 125, 125])
            self.assertEqual(results[1][0][5][1], counter.read_text())
            self.assertEqual(len(results[1][2]), len(inputs))

    def test_separate_daemons_do_not_share_firewall_state(self):
        with tempfile.TemporaryDirectory() as temporary:
            left, env_left = platform(Path(temporary) / 'left', os.environ)
            right, env_right = platform(Path(temporary) / 'right', os.environ)
            with FirewallBroker(left) as a, FirewallBroker(right) as b:
                for root, env, broker, expected in ((left, env_left, a, 0), (right, env_right, b, 1)):
                    env = dict(env, VPNHOTSPOT_FIREWALL_BROKER=broker.name)
                    command = [str(root / 'bin/iptables-restore'), '-w', '--noflush']
                    if expected == 0:
                        subprocess.run(command, input='*filter\n-I X -j RETURN\nCOMMIT\n', text=True, env=env, check=True)
                    result = subprocess.run(command, input='*filter\n-C X -j RETURN\nCOMMIT\n', text=True, env=env)
                    self.assertEqual(result.returncode, expected)
