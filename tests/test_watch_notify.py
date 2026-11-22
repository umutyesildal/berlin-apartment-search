import copy
import io
import json
import sqlite3
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import Mock, patch
from support import OfflineTest, working_directory
from guard import Guard, SourceError
from models import Listing
from notify import destination, main as notify_main, send
from watch import claim_new, main as watch_main, run


class NotifyTests(OfflineTest):
    def test_dry_run_without_secrets_never_fetches(self):
        guard = Mock()
        with patch.dict('os.environ', {}, clear=True):
            self.assertEqual(send(guard, 'telegram', 'New listings', dry_run=True)['status'], 'dry_run')
        guard.fetch.assert_not_called()

    def test_explicit_private_targets_and_guarded_payloads(self):
        guard = Mock()
        guard.fetch.return_value = '{"ok":true}'
        env = {'TELEGRAM_BOT_TOKEN': '123456:fictional-token', 'TELEGRAM_CHAT_ID': '12345'}
        result = send(guard, 'telegram', 'New listings', confirm_self=True, environ=env)
        self.assertEqual(result['status'], 'sent')
        args, kwargs = guard.fetch.call_args
        self.assertEqual(args[0], 'telegram')
        self.assertEqual(json.loads(kwargs['body'])['chat_id'], '12345')
        self.assertNotIn('fictional-token', json.dumps(result))
        guard.fetch.return_value = '{"id":"fictional-notification"}'
        self.assertEqual(send(guard, 'ntfy', 'New listings', confirm_self=True,
                              environ={'NTFY_TOPIC_URL': 'https://ntfy.sh/fictional-private-topic'})['status'], 'sent')
        self.assertEqual(guard.fetch.call_args.args[0], 'ntfy')
        with self.assertRaises(ValueError):
            destination('telegram', False, env)
        for chat in ('-12345', '@channel', ''):
            with self.assertRaises(ValueError):
                destination('telegram', True, dict(env, TELEGRAM_CHAT_ID=chat))
        for url in ('http://ntfy.sh/topic', 'https://attacker.test/topic', 'https://ntfy.sh/topic?extra=1'):
            with self.assertRaises(ValueError):
                destination('ntfy', True, {'NTFY_TOPIC_URL': url})

    def test_failures_do_not_leak_private_values(self):
        guard = Mock()
        env = {'NTFY_TOPIC_URL': 'https://ntfy.sh/fictional-private-topic'}
        for response in ('not json', '{"ok":false}'):
            guard.fetch.return_value = response
            result = send(guard, 'ntfy', 'New listings', confirm_self=True, environ=env)
            self.assertEqual(result['status'], 'failed')
        guard.fetch.side_effect = SourceError('private value must not be exposed')
        result = send(guard, 'ntfy', 'New listings', confirm_self=True, environ=env)
        self.assertEqual(result['status'], 'failed')
        self.assertNotIn('private value', json.dumps(result))
        with tempfile.TemporaryDirectory() as directory, working_directory(directory), patch('sys.stdout', io.StringIO()):
            self.assertEqual(notify_main(['--provider', 'ntfy', '--message', 'New', '--dry-run']), 0)


class WatchTests(OfflineTest):
    def raw_report(self, rows):
        from dedupe import group
        return {'generated_at': '2026-01-01T00:00:00+00:00', 'sources': {'fiction': {'status': 'ok'}},
                'listing_count': len(rows), 'groups': group(rows)}

    def test_first_seen_repeat_and_cross_portal_duplicates(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'watch.sqlite'
            row = Listing('fiction', '1', 'https://example.test/1', 'Fictional', postcode='10115', street='Fiktivweg',
                          rooms=2, area_m2=50, cold_eur=700)
            first, ids = claim_new(self.raw_report([row]), path, notification=True, now='2026-01-01T00:00:00+00:00')
            self.assertEqual(first['new_count'], 1)
            second, _ = claim_new(self.raw_report([row]), path)
            self.assertEqual(second['new_count'], 0)
            other = Listing('other', '2', 'https://example.test/2', 'Same flat', postcode='10115', street='Fiktivweg',
                            rooms=2, area_m2=51, cold_eur=710)
            self.assertEqual(claim_new(self.raw_report([other]), path)[0]['new_count'], 0)
            with sqlite3.connect(path) as db:
                self.assertEqual(db.execute('SELECT first_seen,notified_at FROM seen').fetchone(),
                                 ('2026-01-01T00:00:00+00:00', '2026-01-01T00:00:00+00:00'))

    def test_empty_partial_unknown_and_query_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'watch.sqlite'
            self.assertEqual(claim_new(self.raw_report([]), path)[0]['new_count'], 0)
            rows = [Listing('fiction', str(i), 'https://example.test/detail?id=' + str(i), 'Unknown address') for i in (1, 2)]
            self.assertEqual(claim_new(self.raw_report(rows), path)[0]['new_count'], 2)
            rows[0].source_id = 'new-id'
            rows[0].url += '&utm_source=alert'
            self.assertEqual(claim_new(self.raw_report(rows[:1]), path)[0]['new_count'], 0)

    def test_concurrent_claims_have_only_one_winner(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'watch.sqlite'
            report = self.raw_report([Listing('fiction', '1', '', 'Fictional')])
            with ThreadPoolExecutor(max_workers=2) as executor:
                results = list(executor.map(lambda _: claim_new(copy.deepcopy(report), path)[0]['new_count'], range(2)))
            self.assertEqual(sorted(results), [0, 1])

    def test_one_shot_dry_run_scores_reports_and_suppresses_seen(self):
        with tempfile.TemporaryDirectory() as directory:
            rows = [Listing('fiction', '1', '', 'Fictional flat', warm_eur=1400)]
            with patch('sources.inberlinwohnen.search', return_value=rows), patch('watch.send', return_value={'status': 'dry_run'}) as notify:
                first = run(['inberlinwohnen'], Mock(), directory, provider='ntfy', dry_run=True,
                            profile={'max_warm_eur': 1000}, max_warm=2000)
                second = run(['inberlinwohnen'], Mock(), directory, provider='ntfy', dry_run=True)
            notify.assert_called_once()
            self.assertEqual(first['new_count'], 1)
            self.assertEqual(second['new_count'], 0)
            member = first['groups'][0]['members'][0]
            self.assertEqual(member['fit']['factors']['budget']['points'], 20)
            self.assertIn('first_seen', member['fit']['factors']['freshness']['reason'])
            self.assertTrue((Path(directory) / 'watch/shortlist.html').is_file())
            with sqlite3.connect(Path(directory) / 'watch.sqlite') as db:
                self.assertIsNone(db.execute('SELECT notified_at FROM seen').fetchone()[0])

    def test_failed_send_is_not_retried_and_errors_are_reported(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch('watch.destination'), patch('sources.inberlinwohnen.search', return_value=[Listing('fiction', '1', '', 'Flat')]):
                with patch('watch.send', return_value={'status': 'failed'}) as notify:
                    self.assertEqual(run(['inberlinwohnen'], Mock(), directory, provider='ntfy', confirm_self=True)['notification']['status'], 'failed')
                    run(['inberlinwohnen'], Mock(), directory, provider='ntfy', confirm_self=True)
                    notify.assert_called_once()
            guard = Mock()
            guard.fetch.side_effect = SourceError('offline')
            report = run(['inberlinwohnen'], guard, directory)
            self.assertEqual(report['sources']['inberlinwohnen']['status'], 'error')

    def test_cli_empty_and_bad_configuration(self):
        with tempfile.TemporaryDirectory() as directory, working_directory(directory):
            with patch('sources.inberlinwohnen.search', return_value=[]), patch('sys.stdout', io.StringIO()) as out:
                self.assertEqual(watch_main(['--source', 'inberlinwohnen', '--notify', 'ntfy', '--dry-run']), 0)
                self.assertEqual(json.loads(out.getvalue())['new_count'], 0)
            with patch('sys.stderr', io.StringIO()), self.assertRaises(SystemExit):
                watch_main(['--weights', '{"budget":-1}'])

    def test_guard_rejects_non_delivery_notification_endpoints(self):
        with tempfile.TemporaryDirectory() as directory:
            guard = Guard(directory)
            for site, url in (('telegram', 'https://api.telegram.org/bot123:fictional/getUpdates'),
                              ('ntfy', 'https://ntfy.sh/topic/json')):
                with self.assertRaises(SourceError):
                    guard.fetch(site, url, body=b'{}')
