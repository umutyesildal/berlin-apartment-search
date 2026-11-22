import ast
import io
import json
import tempfile
from pathlib import Path
from unittest.mock import patch
from support import OfflineTest, SCRIPTS, working_directory
from tracker import main


class EncodingTests(OfflineTest):
    def test_tracker_import_uses_utf8_even_with_ascii_system_default(self):
        original = Path.read_text

        def read_with_ascii_default(path, *args, **kwargs):
            kwargs.setdefault('encoding', 'ascii')
            return original(path, *args, **kwargs)

        with tempfile.TemporaryDirectory() as directory, working_directory(directory):
            path = Path(directory) / 'results.json'
            path.write_text(json.dumps({'groups': [{'members': [{'id': 'fiction:1', 'title': 'Schöne Wohnung'}]}]},
                                       ensure_ascii=False), encoding='utf-8')
            with patch.object(Path, 'read_text', read_with_ascii_default), patch('sys.stdout', io.StringIO()):
                self.assertEqual(main(['import', str(path)]), 0)

    def test_all_script_text_file_calls_have_explicit_utf8(self):
        missing = []
        for path in SCRIPTS.rglob('*.py'):
            tree = ast.parse(path.read_text(encoding='utf-8'))
            for node in ast.walk(tree):
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr in ('read_text', 'write_text'):
                    encoding = next((item.value for item in node.keywords if item.arg == 'encoding'), None)
                    if not isinstance(encoding, ast.Constant) or encoding.value != 'utf-8':
                        missing.append('%s:%s' % (path.name, node.lineno))
        self.assertEqual(missing, [])
