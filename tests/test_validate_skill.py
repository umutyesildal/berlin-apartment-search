import json
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path
from unittest.mock import patch
from support import OfflineTest, ROOT
import package_openai
import package_skill
from validate_skill import validate


class StructureTests(OfflineTest):
    def test_environment_variants_are_ignored_except_public_example(self):
        ignored = ['.env', '.env.local', '.env.production', 'nested/.env.local']
        paths = ignored + ['.env.example', 'nested/.env.example']
        result = subprocess.run(['git', 'check-ignore', '--no-index', '--stdin'], cwd=ROOT,
                                input='\n'.join(paths) + '\n', text=True, capture_output=True)
        self.assertEqual(set(result.stdout.splitlines()), set(ignored))

    def test_nested_private_files_are_excluded_from_both_archives(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / 'repo'
            shutil.copytree(ROOT, root, symlinks=True, ignore=shutil.ignore_patterns('.git', 'flat-search', '__pycache__', 'dist'))
            skill = root / 'skills/berlin-apartment-search'
            forbidden = ['assets/nested/flat-search/results.json', 'scripts/flat-search/private.py',
                         'assets/.env.local', 'assets/.env/config.json', 'assets/state.sqlite',
                         'assets/state.db', 'scripts/__pycache__/private.py', 'assets/private.exe']
            for relative in forbidden:
                path = skill / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text('fictional private data', encoding='utf-8')
            with patch('package_skill.ROOT', root), patch('package_openai.ROOT', root), \
                    patch('package_skill.validate', side_effect=lambda: validate(root)):
                canonical = package_skill.package(root / 'dist/skill.zip')
                openai = package_openai.build(root / 'dist/openai.zip')
            for path, prefix in ((canonical, 'berlin-apartment-search/'), (openai, 'skills/berlin-apartment-search/')):
                with self.subTest(archive=path.name), zipfile.ZipFile(path) as archive:
                    names = set(archive.namelist())
                    self.assertIn(prefix + 'SKILL.md', names)
                    self.assertIn(prefix + 'assets/profile.template.json', names)
                    self.assertTrue(all(prefix + relative not in names for relative in forbidden))

    def test_private_directories_are_ignored_at_every_depth(self):
        paths = ['flat-search/results.json', 'skills/berlin-apartment-search/flat-search/results.json',
                 'nested/project/flat-search/profile.json']
        result = subprocess.run(['git', 'check-ignore', '--no-index', '--stdin'], cwd=ROOT,
                                input='\n'.join(paths) + '\n', text=True, capture_output=True)
        self.assertEqual(set(result.stdout.splitlines()), set(paths))

    def test_repository_structure(self):
        self.assertEqual(validate(), [])

    def test_validator_detects_errors(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / 'repo'
            shutil.copytree(ROOT, root, symlinks=True, ignore=shutil.ignore_patterns('.git', 'flat-search', '__pycache__', 'dist'))
            manifest = root / '.codex-plugin/plugin.json'
            data = json.loads(manifest.read_text())
            data['version'] = '9.9.9'
            manifest.write_text(json.dumps(data))
            (root / '.claude/skills/berlin-apartment-search').unlink()
            (root / 'README.md').write_text('[missing](missing.md)')
            errors = validate(root)
            self.assertTrue(any('version mismatch' in error for error in errors))
            self.assertTrue(any('symlink' in error for error in errors))
            self.assertTrue(any('README link' in error for error in errors))
            (root / 'skills/berlin-apartment-search/SKILL.md').unlink()
            self.assertIn('canonical SKILL.md missing', validate(root))

    def test_skill_and_openai_archives_exclude_private_data(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'skill.zip'
            package_skill.package(path)
            with zipfile.ZipFile(path) as archive:
                names = archive.namelist()
                self.assertIn('berlin-apartment-search/SKILL.md', names)
                self.assertTrue(all('flat-search/' not in name and '__pycache__' not in name for name in names))
            with patch('package_openai.package', return_value=path):
                package_openai.build(Path(directory) / 'openai.zip')
            with zipfile.ZipFile(Path(directory) / 'openai.zip') as archive:
                manifest = json.loads(archive.read('.plugin/plugin.json'))
                self.assertEqual(manifest['name'], 'berlin-apartment-search')
                self.assertIn('skills/berlin-apartment-search/SKILL.md', archive.namelist())

    def test_packager_refuses_invalid_structure(self):
        with patch('package_skill.validate', return_value=['synthetic failure']), self.assertRaises(ValueError):
            package_skill.package('unused.zip')
