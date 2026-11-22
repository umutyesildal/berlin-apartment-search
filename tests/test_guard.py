import io
import tempfile
from unittest.mock import Mock, patch
from urllib.error import HTTPError, URLError
from support import OfflineTest, fixture
from guard import Blocked, Deferred, Guard, NoRedirect, SourceError


class GuardTests(OfflineTest):
    def setUp(self):
        super().setUp()
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.now = [100000.0]
        self.delays = []

    def guard(self):
        def sleep(delay):
            self.delays.append(delay)
            self.now[0] += delay
        return Guard(self.directory.name, clock=lambda: self.now[0], sleep=sleep, jitter=lambda: 4)

    def test_persisted_hourly_budget_and_site_isolation(self):
        for _ in range(6):
            self.guard().reserve('a')
        with self.assertRaises(Deferred):
            self.guard().reserve('a')
        self.guard().reserve('b')
        self.assertEqual(self.delays, [4] * 5)
        self.now[0] += 3601
        self.guard().reserve('a')

    def test_daily_budget(self):
        guard = self.guard()
        for _ in range(5):
            for _ in range(6):
                guard.reserve('a')
            self.now[0] += 3601
        with self.assertRaises(Deferred):
            self.guard().reserve('a')
        self.now[0] += 86401
        self.guard().reserve('a')

    def test_escalating_cooldown_survives_reopen(self):
        for duration in (900, 3600, 10800, 43200, 43200):
            with self.assertRaises(Blocked):
                self.guard().block('a', 'test block')
            with self.assertRaises(Deferred):
                self.guard().reserve('a')
            with self.guard().connect() as db:
                until, = db.execute('SELECT until FROM blocks WHERE site=?', ('a',)).fetchone()
            self.assertEqual(until - self.now[0], duration)
            self.now[0] = until + 1

    def test_challenge_and_empty_are_blocked(self):
        for index, body in enumerate(('', fixture('blocked.html'), '<title>Access denied</title>')):
            with self.assertRaises(Blocked):
                self.guard().check_body(str(index), body)
        self.guard().check_body('ok', '<html>Keine Anzeigen gefunden</html>')

    def test_block_from_another_process_during_jitter_is_respected(self):
        def concurrent_block(delay):
            with self.assertRaises(Blocked):
                self.guard().block('a', 'another request was blocked')
        guard = Guard(self.directory.name, clock=lambda: self.now[0],
                      sleep=concurrent_block, jitter=lambda: 4)
        guard.reserve('a')
        with self.assertRaises(Deferred):
            guard.reserve('a')

    def test_fetch_headers_body_and_no_retry(self):
        opener = Mock()
        opener.open.return_value = io.BytesIO(b'{"resultListItems":[],"totalResults":0}')
        with patch('guard.build_opener', return_value=opener) as build:
            body = self.guard().fetch('immoscout', 'https://api.mobile.immobilienscout24.de/search/list',
                                      {'Content-Type': 'application/json'}, b'{}')
        self.assertIn('totalResults', body)
        opener.open.assert_called_once()
        self.assertEqual(opener.open.call_args.args[0].get_method(), 'POST')
        self.assertEqual(opener.open.call_args.args[0].get_header('User-agent'), 'berlin-apartment-search/0.3.1')
        self.assertTrue(any(isinstance(handler, NoRedirect) for handler in build.call_args.args))

    def test_http_errors_and_network_failure(self):
        for code in (403, 429, 302, 500):
            opener = Mock()
            opener.open.side_effect = HTTPError('https://example.invalid', code, 'synthetic', {}, None)
            self.now[0] += 86401
            with patch('guard.build_opener', return_value=opener):
                with self.assertRaises(Blocked if code in (403, 429) else SourceError):
                    self.guard().fetch('kleinanzeigen', 'https://www.kleinanzeigen.de/test')
            opener.open.assert_called_once()
        opener.open.side_effect = URLError('synthetic failure')
        with patch('guard.build_opener', return_value=opener), self.assertRaises(SourceError):
            self.guard().fetch('inberlinwohnen', 'https://www.inberlinwohnen.de/test')

    def test_bad_endpoint_is_not_requested(self):
        for url in ('http://www.kleinanzeigen.de/test', 'https://example.invalid', 'https://www.kleinanzeigen.de:444/test'):
            with patch('guard.build_opener') as build, self.assertRaises(SourceError):
                self.guard().fetch('kleinanzeigen', url)
            build.assert_not_called()

    def test_response_cap(self):
        opener = Mock()
        opener.open.return_value = io.BytesIO(b'x' * (5 * 1024 * 1024 + 1))
        with patch('guard.build_opener', return_value=opener), self.assertRaises(SourceError):
            self.guard().fetch('inberlinwohnen', 'https://www.inberlinwohnen.de/test')
