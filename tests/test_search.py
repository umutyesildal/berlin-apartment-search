import io
import json
import tempfile
from http.client import IncompleteRead, RemoteDisconnected
from pathlib import Path
from unittest.mock import Mock, patch
from support import OfflineTest, fixture
from guard import Blocked, Deferred, Guard, SourceError
from models import Listing
from search import collect, main, markdown, write_report


class SearchTests(OfflineTest):
    def test_mid_body_failure_preserves_other_sources_and_writes_results(self):
        for error in (IncompleteRead(b'partial', 100), RemoteDisconnected('disconnected')):
            with self.subTest(error=type(error).__name__), tempfile.TemporaryDirectory() as directory:
                broken = Mock()
                broken.__enter__ = Mock(return_value=broken)
                broken.__exit__ = Mock(return_value=False)
                broken.read.side_effect = error
                opener = Mock()
                opener.open.side_effect = [broken, io.BytesIO(fixture('kleinanzeigen.html').encode())]
                with patch('search.Path.cwd', return_value=Path(directory)), patch('guard.build_opener', return_value=opener):
                    with patch('sys.stdout', new_callable=io.StringIO):
                        self.assertEqual(main(['--source', 'inberlinwohnen', '--source', 'kleinanzeigen']), 1)
                report = json.loads((Path(directory) / 'flat-search/results.json').read_text())
                self.assertEqual(report['sources']['inberlinwohnen']['status'], 'error')
                self.assertEqual(report['sources']['kleinanzeigen']['returned'], 2)
                self.assertEqual(opener.open.call_count, 2)
                self.assertTrue((Path(directory) / 'flat-search/results.md').is_file())

    def test_fanout_normalization_and_assessments(self):
        guard = Mock()
        guard.fetch.side_effect = [fixture('inberlinwohnen.html'), fixture('kleinanzeigen.html'), fixture('immoscout.json')]
        report = collect(['inberlinwohnen', 'kleinanzeigen', 'immoscout'], guard)
        self.assertEqual(report['listing_count'], 4)
        self.assertEqual(guard.fetch.call_count, 3)
        self.assertTrue(all(status['status'] == 'ok' for status in report['sources'].values()))
        member = report['groups'][0]['members'][0]
        self.assertTrue(member['integrity']['untrusted'])
        self.assertEqual(member['rent']['cold_per_m2'], 11.57)

    def test_filters_keep_unknown_fields(self):
        guard = Mock()
        guard.fetch.return_value = fixture('kleinanzeigen.html')
        report = collect(['kleinanzeigen'], guard, max_warm=500, min_rooms=2, exclude=['swap'])
        self.assertEqual(report['listing_count'], 1)  # asking price is not warm rent
        self.assertEqual(report['sources']['kleinanzeigen']['returned'], 2)

    def test_explicit_empty_is_success(self):
        guard = Mock()
        guard.fetch.return_value = fixture('immoscout-empty.json')
        report = collect(['immoscout'], guard)
        self.assertEqual(report['listing_count'], 0)
        self.assertEqual(report['sources']['immoscout']['status'], 'ok')

    def test_parser_block_persists_and_does_not_hide_other_source(self):
        with tempfile.TemporaryDirectory() as directory:
            guard = Guard(directory)
            with patch.object(guard, 'fetch', side_effect=['<html>Unrecognized page</html>', fixture('kleinanzeigen.html')]):
                report = collect(['inberlinwohnen', 'kleinanzeigen'], guard)
            self.assertTrue(report['sources']['inberlinwohnen']['blocked'])
            self.assertIsNone(report['sources']['inberlinwohnen']['returned'])
            self.assertEqual(report['listing_count'], 2)
            with self.assertRaises(Deferred):
                Guard(directory).reserve('inberlinwohnen')

    def test_fetch_block_not_counted_twice(self):
        with tempfile.TemporaryDirectory() as directory:
            guard = Guard(directory)
            def blocked(*args, **kwargs):
                guard.block('kleinanzeigen', 'synthetic')
            with patch.object(guard, 'fetch', side_effect=blocked):
                report = collect(['kleinanzeigen'], guard)
            self.assertEqual(report['sources']['kleinanzeigen']['status'], 'blocked')
            with guard.connect() as db:
                self.assertEqual(db.execute('SELECT strikes FROM blocks').fetchone()[0], 1)

    def test_source_errors_and_deferred_reported(self):
        for error, status in ((Deferred('budget'), 'deferred'), (SourceError('bad shape'), 'error')):
            guard = Mock()
            guard.fetch.side_effect = error
            report = collect(['inberlinwohnen'], guard)
            self.assertEqual(report['sources']['inberlinwohnen']['status'], status)
            self.assertIsNone(report['sources']['inberlinwohnen']['returned'])

    def test_json_and_markdown_outputs_escape_external_text(self):
        guard = Mock()
        with patch('sources.inberlinwohnen.search', return_value=[Listing('test', '1', 'javascript:bad',
                                                                        '<img src=x> [run](bad)\n# title')]):
            report = collect(['inberlinwohnen'], guard)
        rendered = markdown(report)
        self.assertNotIn('<img', rendered)
        self.assertNotIn('[run](bad)', rendered)
        self.assertIn('&lt;img', rendered)
        with tempfile.TemporaryDirectory() as directory:
            write_report(report, directory)
            self.assertEqual(json.loads((Path(directory) / 'results.json').read_text())['listing_count'], 1)
            self.assertEqual((Path(directory) / 'results.md').read_text(), rendered)

    def test_cli_status_and_duplicate_source(self):
        with tempfile.TemporaryDirectory() as directory, patch('search.Path.cwd', return_value=Path(directory)):
            with patch('guard.Guard.fetch', return_value=fixture('inberlinwohnen-empty.html')) as fetch:
                with patch('sys.stdout', new_callable=io.StringIO):
                    self.assertEqual(main(['--source', 'inberlinwohnen', '--source', 'inberlinwohnen']), 0)
                fetch.assert_called_once()
            with patch('guard.Guard.fetch', side_effect=SourceError('synthetic')):
                with patch('sys.stdout', new_callable=io.StringIO):
                    self.assertEqual(main(['--source', 'inberlinwohnen']), 1)

    def test_cli_rejects_bad_arguments_without_network(self):
        for args in (['--max-warm', '-1'], ['--min-rooms', 'nan'], ['--exclude', 'invalid'], ['--source', 'invalid']):
            with patch('sys.stderr', new_callable=io.StringIO), self.assertRaises(SystemExit) as raised:
                main(args)
            self.assertEqual(raised.exception.code, 2)
