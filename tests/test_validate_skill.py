import json
import shutil
import tempfile
import zipfile
from pathlib import Path
from unittest.mock import patch
from support import OfflineTest, ROOT
import package_openai
import package_skill
from validate_skill import validate


class StructureTests(OfflineTest):
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
