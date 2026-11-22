import io
import os
import stat
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch
from support import ROOT, SCRIPTS, OfflineTest, working_directory
from alerts import main as alerts_main
from commute import Commute
from draft import main as draft_main
from guard import Guard
from import_page import build_report, main as page_main
from report import write as write_shortlist
from search import write_report
from tracker import upsert
from watch import claim_new
from private_paths import private_directory


class PrivatePathTests(OfflineTest):
    def test_outer_flat_search_folder_and_checkout_are_never_chmodded(self):
        if os.name == 'nt':
            self.skipTest('POSIX directory modes')
        with tempfile.TemporaryDirectory() as directory:
            outer = Path(directory) / 'flat-search'
            checkout = outer / 'checkout'
            checkout.mkdir(parents=True)
            outer.chmod(0o755)
            checkout.chmod(0o755)
            with working_directory(checkout):
                Path('flat-search').mkdir()
                Path('flat-search').chmod(0o755)
                private_directory('flat-search/nested/output')
                private_directory('.')
                private_directory(outer)
                self.assertEqual(stat.S_IMODE(outer.stat().st_mode), 0o755)
                self.assertEqual(stat.S_IMODE(checkout.stat().st_mode), 0o755)
                for path in (Path('flat-search'), Path('flat-search/nested'), Path('flat-search/nested/output')):
                    self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o700)

    def test_helper_preserves_outside_parents_and_propagates_errors(self):
        with tempfile.TemporaryDirectory() as directory, working_directory(directory):
            parent = Path(directory)
            mode = stat.S_IMODE(parent.stat().st_mode)
            private_directory(parent / 'flat-search/a/b')
            self.assertEqual(stat.S_IMODE(parent.stat().st_mode), mode)
            with patch.object(Path, 'chmod', side_effect=PermissionError('fixture')):
                with self.assertRaises(PermissionError):
                    private_directory(parent / 'flat-search')

    def test_all_writers_secure_nested_private_directories_and_existing_root(self):
        report = build_report([], 'fixture')
        writers = [lambda: alerts_main([str(ROOT / 'tests/fixtures/alert_immowelt.eml')]),
                   lambda: page_main([str(ROOT / 'tests/fixtures/saved_page.html')]),
                   lambda: write_report(report, 'flat-search/nested/search'),
                   lambda: write_shortlist(report, 'flat-search/nested/report'),
                   lambda: Guard('flat-search/nested/guard'),
                   lambda: Commute(Mock(fetch=Mock(return_value='{}')), 'flat-search/nested').cached('fixture', 'fixture', 10),
                   lambda: upsert('flat-search/nested/tracker.csv', []),
                   lambda: claim_new(report, 'flat-search/nested/watch.sqlite'),
                   lambda: draft_main(['--profile', str(SCRIPTS.parent / 'assets/profile.template.json'),
                                       '--output', 'flat-search/nested/draft.txt'])]
        if os.name == 'nt':
            self.skipTest('POSIX directory modes')
        previous_umask = os.umask(0o022)
        try:
            for existing in (False, True):
                for index, write in enumerate(writers):
                    with self.subTest(existing=existing, writer=index), tempfile.TemporaryDirectory() as directory:
                        with working_directory(directory), patch('sys.stdout', io.StringIO()):
                            root = Path('flat-search')
                            if existing:
                                root.mkdir(mode=0o755)
                                root.chmod(0o755)
                            write()
                            for path in [root] + [item for item in root.rglob('*') if item.is_dir()]:
                                self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o700, str(path))
        finally:
            os.umask(previous_umask)
