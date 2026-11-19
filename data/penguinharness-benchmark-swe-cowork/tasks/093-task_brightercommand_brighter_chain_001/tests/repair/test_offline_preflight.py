import json
from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
PREFLIGHT = ROOT / 'environment/offline-preflight.py'


class OfflinePreflightTests(unittest.TestCase):
    def run_preflight(self, mode, package_names=(), reference='Example.Package', project_name='Example'):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            repo = root / 'repo'
            assets = root / 'assets'
            packages = root / 'packages'
            profile = root / 'offline-net10.targets'
            focused = root / 'focused-projects.txt'
            project = repo / 'src' / project_name
            project.mkdir(parents=True)
            assets.mkdir()
            packages.mkdir()
            (project / (project_name + '.csproj')).write_text(
                f'<Project><ItemGroup><PackageReference Include="{reference}" />'
                '</ItemGroup></Project>')
            profile.write_text(
                '<Project><ItemGroup Condition="\'$(MSBuildProjectName)\' == '
                '\'Paramore.Brighter.Extensions.DependencyInjection\'">'
                '<PackageReference Remove="System.Text.Json" />'
                '<FrameworkReference Include="Microsoft.AspNetCore.App" />'
                '</ItemGroup></Project>')
            focused.write_text(f'src/{project_name}/{project_name}.csproj\n')
            for package_name in package_names:
                (packages / package_name.lower() / '1.0.0').mkdir(parents=True)
            result = subprocess.run([
                'python3', str(PREFLIGHT), '--repo', str(repo), '--assets', str(assets),
                '--packages', str(packages), '--profile', str(profile),
                '--focused-file', str(focused), '--mode', mode,
            ], text=True, capture_output=True, check=False)
            return result

    def test_missing_package_is_reported_without_network_fallback(self):
        result = self.run_preflight('focused')
        self.assertEqual(78, result.returncode)
        report = json.loads(result.stdout)
        self.assertEqual('missing_offline_inputs', report['status'])
        self.assertIn('missing package cache Example.Package', report['problems'][0])

    def test_present_package_passes(self):
        result = self.run_preflight('focused', ['Example.Package'])
        self.assertEqual(0, result.returncode)
        self.assertEqual('ok', json.loads(result.stdout)['status'])

    def test_profile_replacements_only_apply_to_the_di_project(self):
        result = self.run_preflight('focused', reference='System.Text.Json')
        self.assertEqual(78, result.returncode)
        self.assertIn('missing package cache System.Text.Json', json.loads(result.stdout)['problems'][0])
        result = self.run_preflight('focused', reference='System.Text.Json',
                                    project_name='Paramore.Brighter.Extensions.DependencyInjection')
        self.assertEqual(0, result.returncode)

    def test_missing_restore_assets_are_explicitly_not_version_validated(self):
        result = self.run_preflight('focused', ['Example.Package'])
        report = json.loads(result.stdout)
        self.assertEqual(['src/Example/Example.csproj'], report['projects_without_restore_assets'])
        self.assertIn('not MSBuild evaluation', report['validation_scope'])


if __name__ == '__main__':
    unittest.main()
