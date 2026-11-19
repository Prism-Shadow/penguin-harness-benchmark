import tempfile
import unittest
from pathlib import Path

from prepare_candidate_dependencies import copy_source, CandidateDependencyError


class SourceSnapshotTests(unittest.TestCase):
    def test_preserves_source_directories_and_excludes_generated_outputs(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, output = root / 'source', root / 'snapshot'
            source.mkdir()
            included = ['src/js/build/helper.js', 'src/js/tests/helper.js',
                        'packages/helper/dist/index.js', 'src/vendor/helper.js',
                        'vendor/entry.js', 'dist/helper.js', 'build/configuration.cjs',
                        'target/entry.js', 'coverage/helper.js', 'logs/helper.js']
            excluded = ['build/tms-temp/generated.js', 'build/tgut-temp/generated.js',
                        'build/zip/archive.zip', 'build/crx/archive.crx',
                        'node_modules/dependency/index.js', 'src/js/gsOauthSecrets.local.js', 'key.pem']
            for name in included + excluded:
                path = source / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(name)
            copy_source(source, output)
            actual = sorted(str(path.relative_to(output)) for path in output.rglob('*') if path.is_file())
            self.assertEqual(actual, sorted(included))
            for name in included:
                self.assertEqual((output / name).read_text(), name)

    def test_repository_relative_links_work_without_host_sources(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, output = root / 'source', root / 'snapshot'
            source.mkdir()
            (source / 'helper.js').write_text('export const answer = 42;')
            (source / 'entry.js').symlink_to('helper.js')
            copy_source(source, output)
            self.assertEqual((output / 'entry.js').read_text(), (source / 'helper.js').read_text())
            self.assertEqual((output / 'entry.js').resolve(), output / 'helper.js')

    def test_escape_link_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'source'
            source.mkdir()
            (root / 'not-submitted.js').write_text('outside checkout')
            (source / 'entry.js').symlink_to('../not-submitted.js')
            with self.assertRaises(CandidateDependencyError):
                copy_source(source, root / 'snapshot')


if __name__ == '__main__':
    unittest.main()
