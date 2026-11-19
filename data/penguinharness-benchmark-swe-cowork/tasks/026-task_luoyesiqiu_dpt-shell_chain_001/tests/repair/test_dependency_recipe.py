import hashlib
import importlib.util
import io
import json
import os
import stat
import subprocess
import tarfile
import tempfile
import unittest
import urllib.error
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("dependency_recipe", ROOT / "environment/build-inputs/acquire.py")
RECIPE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RECIPE)


class Response(io.BytesIO):
    url = "https://dl.google.com/test-input"
    status = 200
    headers = {}


class DependencyRecipeTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_official_provenance_and_redirect_policy(self):
        for url in ("https://dl.google.com/android/repository/file.zip", "https://codeload.github.com/zlib-ng/minizip-ng/tar.gz/commit"):
            self.assertEqual(RECIPE.official_url(url), url)
        for url in ("http://dl.google.com/file", "https://evil.example/file", "https://dl.google.com@evil.example/file",
                    "https://user:secret@dl.google.com/file", "https://dl.google.com:123/file"):
            with self.subTest(url=url), self.assertRaises(RECIPE.RecipeError):
                RECIPE.official_url(url)

    def test_download_records_actual_bytes_and_replays_without_network(self):
        downloads = RECIPE.Downloads(self.root)
        data = b"small transport fixture, not a dependency payload"
        expected = hashlib.sha256(data).hexdigest()
        with patch.object(downloads.opener, "open", return_value=Response(data)) as opening:
            downloaded = downloads.fetch("artifact", Response.url, expected)
            self.assertEqual(downloaded.read_bytes(), data)
            self.assertEqual(opening.call_count, 1)
        document = json.loads((self.root / "downloads.json").read_text())
        self.assertEqual(document["artifact"]["sha256"], expected)
        replay = RECIPE.Downloads(self.root, document)
        with patch.object(replay.opener, "open", side_effect=AssertionError("unexpected network")):
            self.assertEqual(replay.fetch("artifact", Response.url), downloaded)
        downloaded.write_bytes(b"changed")
        with self.assertRaisesRegex(RECIPE.RecipeError, "changed cached"):
            replay.fetch("artifact", Response.url)

    def test_download_checksum_size_and_lock_mismatch_fail_closed(self):
        downloads = RECIPE.Downloads(self.root)
        with patch.object(downloads.opener, "open", return_value=Response(b"data")):
            with self.assertRaisesRegex(RECIPE.RecipeError, "checksum mismatch"):
                downloads.fetch("bad-checksum", Response.url, "0" * 64)
        with patch.object(downloads.opener, "open", return_value=Response(b"data")):
            with self.assertRaisesRegex(RECIPE.RecipeError, "byte limit"):
                downloads.fetch("too-big", Response.url, limit=2)
        self.assertFalse((downloads.root / "too-big").exists())
        self.assertFalse((downloads.root / "too-big.part").exists())
        replay = RECIPE.Downloads(self.root, {"bad-checksum": {"url": Response.url, "sha256": "0" * 64}})
        with patch.object(replay.opener, "open", return_value=Response(b"data")):
            with self.assertRaisesRegex(RECIPE.RecipeError, "locked checksum"):
                replay.fetch("bad-checksum", Response.url)

    def test_sdk_metadata_exact_revision_linux_checksum_and_license(self):
        namespace = "http://schemas.android.com/repository/android/common/01"
        document = ET.fromstring(f'''<sdk-repository xmlns="{namespace}">
            <license id="android-sdk-license">Android SDK License</license>
            <remotePackage path="platforms;android-33">
              <revision><major>3</major><minor>0</minor><micro>0</micro></revision>
              <channelRef ref="channel-1"/>
              <uses-license ref="android-sdk-license"/><archives>
                <archive><host-os>linux</host-os><host-bits>64</host-bits><complete>
                  <checksum type="sha1">{'b' * 40}</checksum><url>preview-platform.zip</url>
                </complete></archive>
              </archives>
            </remotePackage>
            <remotePackage path="platforms;android-33">
              <revision><major>3</major><minor>0</minor><micro>0</micro></revision>
              <channelRef ref="channel-0"/>
              <uses-license ref="android-sdk-license"/><archives>
                <archive><host-os>windows</host-os><host-bits>64</host-bits><complete>
                  <checksum type="sha1">{'c' * 40}</checksum><url>wrong-platform.zip</url>
                </complete></archive>
                <archive><host-os>linux</host-os><host-bits>32</host-bits><complete>
                  <checksum type="sha1">{'d' * 40}</checksum><url>platform-33_r03-linux-32.zip</url>
                </complete></archive>
                <archive><host-os>linux</host-os><host-bits>64</host-bits><complete>
                  <checksum type="sha1">{'a' * 40}</checksum><url>platform-33_r03.zip</url>
                </complete></archive>
              </archives>
            </remotePackage>
            <remotePackage path="platforms;android-33">
              <revision><major>2</major><minor>0</minor><micro>0</micro></revision>
              <channelRef ref="channel-0"/>
              <uses-license ref="android-sdk-license"/><archives>
                <archive><host-os>linux</host-os><complete>
                  <checksum type="sha1">{'e' * 40}</checksum><url>old-platform.zip</url>
                </complete></archive>
              </archives>
            </remotePackage>
            </sdk-repository>''')
        record = RECIPE.package_record(document, "platforms;android-33", "3")
        self.assertEqual(record, ("https://dl.google.com/android/repository/platform-33_r03.zip",
                                  "a" * 40, "sha1", "android-sdk-license"))
        with self.assertRaisesRegex(RECIPE.RecipeError, "revision changed"):
            RECIPE.package_record(document, "platforms;android-33", "21.4")
        with self.assertRaisesRegex(RECIPE.RecipeError, "absent"):
            RECIPE.package_record(document, "platforms;missing", "3")

        stable = next(element for element in document.iter()
                       if RECIPE.xml_name(element) == "remotePackage"
                       and element.get("path") == "platforms;android-33"
                       and any(child.get("ref") == "channel-0"
                               for child in RECIPE.xml_children(element, "channelRef")))
        revision = RECIPE.xml_child(stable, "revision", "revision")
        ET.SubElement(revision, f"{{{namespace}}}preview").text = "1"
        with self.assertRaisesRegex(RECIPE.RecipeError, "channel"):
            RECIPE.package_record(document, "platforms;android-33", "3")

        license_copy = ET.fromstring(ET.tostring(document))
        license_node = next(element for element in license_copy.iter()
                            if RECIPE.xml_name(element) == "license")
        license_node.text = ""
        stable_copy = next(element for element in license_copy.iter()
                           if RECIPE.xml_name(element) == "remotePackage"
                           and element.get("path") == "platforms;android-33"
                           and any(child.get("ref") == "channel-0"
                                   for child in RECIPE.xml_children(element, "channelRef")))
        revision_copy = RECIPE.xml_child(stable_copy, "revision", "revision")
        for preview in RECIPE.xml_children(revision_copy, "preview"):
            revision_copy.remove(preview)
        with self.assertRaisesRegex(RECIPE.RecipeError, "license is empty"):
            RECIPE.package_record(license_copy, "platforms;android-33", "3")

    def test_real_zip_extract_preserves_mode_and_materializes_internal_link(self):
        archive = self.root / "input.zip"
        executable = zipfile.ZipInfo("distribution/bin/tool")
        executable.external_attr = (stat.S_IFREG | 0o755) << 16
        linked = zipfile.ZipInfo("distribution/bin/alias")
        linked.external_attr = (stat.S_IFLNK | 0o777) << 16
        with zipfile.ZipFile(archive, "w") as stream:
            stream.writestr(executable, b"#!/bin/sh\nprintf fixture")
            stream.writestr(linked, "tool")
        destination = self.root / "expanded"
        RECIPE.unpack(archive, destination)
        self.assertFalse((destination / linked.filename).is_symlink())
        self.assertTrue(os.access(destination / linked.filename, os.X_OK))
        result = subprocess.run([str(destination / linked.filename)], capture_output=True, check=True)
        self.assertEqual(result.stdout, b"fixture")

    def test_sdk_flat_and_wrapped_archives_preserve_package_contents(self):
        for layout in ("flat", "wrapped"):
            with self.subTest(layout=layout):
                prefix = "" if layout == "flat" else "distribution/"
                archive = self.root / (layout + ".zip")
                executable = zipfile.ZipInfo(prefix + "bin/cmake")
                executable.external_attr = (stat.S_IFREG | 0o755) << 16
                with zipfile.ZipFile(archive, "w") as stream:
                    stream.writestr(prefix + "source.properties", "Pkg.Revision = 3.18.1\n")
                    stream.writestr(prefix + "NOTICE", "package notice")
                    stream.writestr(prefix + "share/cmake-3.18/Modules/module.cmake", "module content")
                    stream.writestr(executable, b"#!/bin/sh\nprintf sdk-fixture")
                extracted = self.root / layout
                RECIPE.unpack(archive, extracted)
                root = RECIPE.sdk_package_root(extracted, "cmake;3.18.1", "3.18.1")
                self.assertEqual(root, extracted if layout == "flat" else extracted / "distribution")
                self.assertEqual((root / "NOTICE").read_text(), "package notice")
                self.assertEqual((root / "share/cmake-3.18/Modules/module.cmake").read_text(), "module content")
                result = subprocess.run([str(root / "bin/cmake")], capture_output=True, check=True)
                self.assertEqual(result.stdout, b"sdk-fixture")

    def test_sdk_archive_missing_or_ambiguous_roots_are_rejected(self):
        for layout, files in {
            "missing": {"bin/cmake": "tool"},
            "empty": {},
            "multiple": {"one/source.properties": "Pkg.Revision=3", "two/source.properties": "Pkg.Revision=3"},
            "nested": {"outer/inner/source.properties": "Pkg.Revision=3"},
            "unclaimed": {"package/source.properties": "Pkg.Revision=3", "NOTICE": "outside package"},
        }.items():
            with self.subTest(layout=layout):
                root = self.root / layout
                root.mkdir()
                for name, content in files.items():
                    target = root / name
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_text(content)
                with self.assertRaises(RECIPE.RecipeError):
                    RECIPE.sdk_package_root(root, "platforms;android-33", "3")

    def test_sdk_archive_revision_must_match_selected_metadata(self):
        properties = self.root / "source.properties"
        for revision in ("3", "3.0.0"):
            properties.write_text("Pkg.Revision = " + revision + "\n")
            self.assertEqual(RECIPE.sdk_package_root(self.root, "platforms;android-33", "3"), self.root)
        for content in ("Pkg.Revision=2", "Pkg.Revision=3.0.1", "Pkg.Revision=3-preview",
                        "Pkg.Revision=3\nPkg.Revision=3", "Pkg.Desc=platform", "Pkg.Revision=\n"):
            with self.subTest(content=content), self.assertRaises(RECIPE.RecipeError):
                properties.write_text(content)
                RECIPE.sdk_package_root(self.root, "platforms;android-33", "3")

    def test_acquisition_places_all_sdk_layouts_before_compatibility_gate(self):
        versions = json.loads((RECIPE.ROOT / "versions.json").read_text())
        document = ET.Element("sdk-repository")
        ET.SubElement(document, "license", id="sdk-license").text = "SDK fixture license"
        payloads = {}
        sdk_files = {"platforms;android-33": "android.jar", "build-tools;29.0.2": "aapt",
                     "cmake;3.18.1": "bin/cmake", "ndk;21.1.6352462": "ndk-build"}
        for package, revision in versions["sdk_packages"].items():
            contents = io.BytesIO()
            prefix = "" if package.startswith("cmake;") else "distribution/"
            with zipfile.ZipFile(contents, "w") as stream:
                stream.writestr(prefix + "source.properties", "Pkg.Revision=" + revision)
                stream.writestr(prefix + sdk_files[package], "fixture for " + package)
                stream.writestr(prefix + "NOTICE", "notice for " + package)
            filename = package.replace(";", "-") + ".zip"
            payloads["https://dl.google.com/android/repository/" + filename] = contents.getvalue()
            remote = ET.SubElement(document, "remotePackage", path=package)
            revision_node = ET.SubElement(remote, "revision")
            for component, value in zip(("major", "minor", "micro"), revision.split(".")):
                ET.SubElement(revision_node, component).text = value
            ET.SubElement(remote, "uses-license", ref="sdk-license")
            archive = ET.SubElement(ET.SubElement(remote, "archives"), "archive")
            ET.SubElement(archive, "host-os").text = "linux"
            complete = ET.SubElement(archive, "complete")
            ET.SubElement(complete, "checksum", type="sha256").text = hashlib.sha256(contents.getvalue()).hexdigest()
            ET.SubElement(complete, "url").text = filename
        payloads["https://dl.google.com/android/repository/repository2-1.xml"] = ET.tostring(document)

        def respond(request, timeout):
            if request.full_url.startswith("https://api.github.com/"):
                raise RECIPE.RecipeError("SDK fixture boundary; not a compatibility result")
            response = Response(payloads[request.full_url])
            response.url = request.full_url
            return response

        arguments = type("Arguments", (), {"work": self.root / "work", "output": self.root / "bundle",
                                          "lock": None, "java_home": None})()
        opener = RECIPE.urllib.request.build_opener()
        with patch.object(RECIPE.urllib.request, "build_opener", return_value=opener), \
                patch.object(opener, "open", side_effect=respond), \
                self.assertRaisesRegex(RECIPE.RecipeError, "SDK fixture boundary"):
            RECIPE.acquire(arguments)
        for package, relative in sdk_files.items():
            root = arguments.work / "stage/sdk" / package.replace(";", "/")
            self.assertEqual((root / relative).read_text(), "fixture for " + package)
            self.assertEqual((root / "NOTICE").read_text(), "notice for " + package)
            self.assertFalse((root / "distribution").exists())
        records = json.loads((arguments.work / "downloads.json").read_text())
        self.assertEqual(len(records), 5)
        for record in records.values():
            self.assertEqual(record["sha256"], hashlib.sha256(payloads[record["url"]]).hexdigest())
        license_hashes = (arguments.work / "stage/sdk/licenses/sdk-license").read_text().splitlines()
        self.assertEqual(license_hashes, [hashlib.sha1(b"SDK fixture license").hexdigest()] * 4)
        self.assertFalse(arguments.output.exists())
        self.assertFalse((arguments.work / "stage/manifest.json").exists())

    def test_archive_traversal_escape_and_size_rejected(self):
        for name in ("../../escape", "/absolute", "directory\\escape"):
            with self.subTest(name=name), self.assertRaises(RECIPE.RecipeError):
                RECIPE.member_path(self.root, name)
        archive = self.root / "escape.zip"
        linked = zipfile.ZipInfo("alias")
        linked.external_attr = (stat.S_IFLNK | 0o777) << 16
        with zipfile.ZipFile(archive, "w") as stream:
            stream.writestr(linked, "../outside")
        with self.assertRaisesRegex(RECIPE.RecipeError, "escapes"):
            RECIPE.unpack(archive, self.root / "escape-output")
        with self.assertRaisesRegex(RECIPE.RecipeError, "byte limit"):
            RECIPE.unpack(archive, self.root / "oversize-output", limit=1)

    def test_real_tar_extract_and_special_file_rejection(self):
        archive = self.root / "input.tar.gz"
        with tarfile.open(archive, "w:gz") as stream:
            member = tarfile.TarInfo("source/CMakeLists.txt")
            member.size = 7
            stream.addfile(member, io.BytesIO(b"fixture"))
        RECIPE.unpack(archive, self.root / "source")
        self.assertEqual(RECIPE.single_root(self.root / "source").name, "source")
        with tarfile.open(archive, "w:gz") as stream:
            member = tarfile.TarInfo("special")
            member.type = tarfile.FIFOTYPE
            stream.addfile(member)
        with self.assertRaisesRegex(RECIPE.RecipeError, "special"):
            RECIPE.unpack(archive, self.root / "special")

    def test_acquisition_network_failure_never_publishes_manifest(self):
        arguments = type("Arguments", (), {"work": self.root / "work", "output": self.root / "bundle",
                                          "lock": None, "java_home": None})()
        with patch.object(RECIPE.Downloads, "fetch", side_effect=urllib.error.URLError("offline fixture")):
            with self.assertRaises(urllib.error.URLError):
                RECIPE.acquire(arguments)
        self.assertFalse(arguments.output.exists())
        self.assertTrue((arguments.work / "recipe.sha256").is_file())

    def test_existing_work_or_output_is_not_overwritten(self):
        arguments = type("Arguments", (), {"work": self.root / "work", "output": self.root / "bundle",
                                          "lock": None, "java_home": None})()
        arguments.work.mkdir()
        marker = arguments.work / "unrelated"
        marker.write_text("preserve")
        with self.assertRaisesRegex(RECIPE.RecipeError, "work must be new"):
            RECIPE.acquire(arguments)
        self.assertEqual(marker.read_text(), "preserve")

    def test_wrapper_key_uses_gradle_unsigned_base36_algorithm(self):
        self.assertEqual(RECIPE.GRADLE_WRAPPER_URL,
                         "https://services.gradle.org/distributions/gradle-6.5-bin.zip")
        self.assertEqual(RECIPE.GRADLE_TRANSFER_URL,
                         "https://downloads.gradle.org/distributions/gradle-6.5-bin.zip")
        self.assertNotEqual(RECIPE.GRADLE_WRAPPER_URL, RECIPE.GRADLE_TRANSFER_URL)
        for url in (RECIPE.GRADLE_WRAPPER_URL, RECIPE.GRADLE_TRANSFER_URL):
            self.assertEqual(RECIPE.official_url(url), url)
        self.assertEqual(int(RECIPE.wrapper_key(RECIPE.GRADLE_WRAPPER_URL), 36),
                         int(hashlib.md5(RECIPE.GRADLE_WRAPPER_URL.encode()).hexdigest(), 16))


if __name__ == "__main__":
    unittest.main()
