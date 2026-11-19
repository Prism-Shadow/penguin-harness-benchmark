from pathlib import Path
import os
import subprocess
import tempfile
import unittest

from native_environment import NativeEnvironmentError, build_native_stubs, validate_native_stubs

ROOT = Path(__file__).resolve().parent


class NativeEnvironmentTests(unittest.TestCase):
    def test_image_and_verifier_use_identical_source(self):
        self.assertEqual((ROOT / "environment/android_stubs.c").read_bytes(),
                         Path(os.environ.get('VPNHOTSPOT_IMAGE_ABI_SOURCE', '/opt/vpn-environment/android_stubs.c')).read_bytes())

    def test_legacy_archived_libraries_are_rejected(self):
        with self.assertRaisesRegex(NativeEnvironmentError, "missing Android ABI symbol"):
            validate_native_stubs(ROOT / "environment")

    def test_linked_abi_and_descriptor_lifecycle(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            library = build_native_stubs(ROOT / "environment", root)
            self.assertEqual(build_native_stubs(ROOT / "environment", root), library)
            executable = root / "abi-check"
            command = ["cc", "-Wall", "-Wextra", "-Werror", str(ROOT / "environment/native_abi_smoke.c"),
                       "-L", str(library), "-Wl,-rpath," + str(library), "-landroid", "-llog",
                       "-o", str(executable)]
            subprocess.run(command, check=True)
            subprocess.run([str(executable)], check=True)


if __name__ == "__main__":
    unittest.main()
