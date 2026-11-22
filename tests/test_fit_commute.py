import io
import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
from unittest.mock import Mock, patch
from support import OfflineTest
from commute import Commute, coordinates, main as commute_main
from fit_score import WEIGHTS, main as fit_main, score
from guard import Blocked, Deferred, Guard, SourceError


class FitTests(OfflineTest):
    def test_missing_neutral_and_all_reasons(self):
        result = score({})
        self.assertEqual(result['score'], 50)
        self.assertEqual(set(result['factors']), set(WEIGHTS))
        self.assertTrue(all(f['status'] == 'unknown' and f['reason'] for f in result['factors'].values()))
        self.assertEqual(score({'scam': {'score': 20}, 'rent': {'costs_review': True}}), result)
        self.assertEqual(score({'costs_eur': 0, 'area_m2': 50})['factors']['costs']['points'], 0)

    def test_preferences_dates_and_commute(self):
        profile = {'max_warm_eur': 1200, 'min_area_m2': 50, 'min_rooms': 2, 'districts': ['Mitte'],
                   'value_eur_m2': 15, 'max_commute_minutes': 40}
        listing = {'warm_eur': 1100, 'area_m2': 60, 'rooms': 2, 'district': 'mitte', 'cold_eur': 900,
                   'costs_eur': 150, 'posted_at': '2026-01-01', 'commute': {'status': 'ok', 'minutes': 30}}
        result = score(listing, profile, now=datetime(2026, 1, 1, tzinfo=timezone.utc))
        self.assertEqual(result['score'], 95)
        self.assertTrue(all(f['status'] == 'known' for f in result['factors'].values()))
        self.assertLess(score(dict(listing, warm_eur=2000, district='Elsewhere', posted_at='2025-01-01'), profile)['score'], 95)
        self.assertEqual(score({'posted_at': 'tomorrow'})['factors']['freshness']['status'], 'unknown')
        self.assertEqual(score({'posted_at': '2999-01-01'})['factors']['freshness']['status'], 'unknown')

    def test_weights_and_cli(self):
        overrides = dict.fromkeys(WEIGHTS, 0)
        overrides['budget'] = 1
        self.assertEqual(score({'warm_eur': 500}, {'max_warm_eur': 1000}, overrides)['score'], 100)
        for invalid in ([], {'bad': 1}, {'budget': -1}, {'budget': float('nan')}, dict.fromkeys(WEIGHTS, 0)):
            with self.assertRaises(ValueError):
                score({}, weights=invalid)
        with patch('sys.stdin', io.StringIO('{}')), patch('sys.stdout', io.StringIO()) as out:
            self.assertEqual(fit_main([]), 0)
            self.assertEqual(json.loads(out.getvalue())['score'], 50)


class CommuteTests(OfflineTest):
    def test_bike_direct_duration_uses_limit_seconds_and_caps_at_90_minutes(self):
        with tempfile.TemporaryDirectory() as directory:
            guard = Mock()

            def route_response(site, url, **kwargs):
                query = parse_qs(urlsplit(url).query, keep_blank_values=True)
                maximum = int(query.get('maxDirectTime', ['1800'])[0])
                return json.dumps({'direct': [{'duration': 2700, 'legs': [{'mode': 'BIKE'}]}]
                                   if maximum >= 2700 else [], 'itineraries': []})

            guard.fetch.side_effect = route_response
            client = Commute(guard, directory)
            result = client.route([52, 13], [52.1, 13.1], mode='bike')
            self.assertEqual(result['status'], 'ok')
            self.assertEqual(result['minutes'], 45)
            for maximum, seconds in ((60, 3600), (120, 5400)):
                client.route([52 + maximum / 10000, 13], [52.1, 13.1], mode='bike', max_minutes=maximum)
                query = parse_qs(urlsplit(guard.fetch.call_args.args[1]).query)
                self.assertEqual(query['maxDirectTime'], [str(seconds)])
            for invalid in (0, -1, True, float('nan')):
                self.assertEqual(client.route([52, 13], [52.1, 13.1], mode='bike', max_minutes=invalid)['status'], 'unknown')

    def test_bike_uses_direct_bike_routes_not_transit_itineraries(self):
        with tempfile.TemporaryDirectory() as directory:
            guard = Mock()
            guard.fetch.return_value = json.dumps({'direct': [{'duration': 900, 'legs': [{'mode': 'BIKE'}]}],
                                                  'itineraries': [{'duration': 120, 'legs': [{'mode': 'BUS'}]}]})
            result = Commute(guard, directory).route([52, 13], [52.1, 13.1], mode='bike')
            self.assertEqual(result['minutes'], 15)
            query = parse_qs(urlsplit(guard.fetch.call_args.args[1]).query, keep_blank_values=True)
            self.assertEqual(query['directModes'], ['BIKE'])
            self.assertEqual(query['transitModes'], [''])

    def test_bike_without_direct_bike_result_is_unknown(self):
        with tempfile.TemporaryDirectory() as directory:
            guard = Mock()
            guard.fetch.return_value = json.dumps({'direct': [], 'itineraries': [{'duration': 120}]})
            self.assertEqual(Commute(guard, directory).route([52, 13], [52.1, 13.1], mode='bike')['status'], 'unknown')

    def test_geocode_route_cache_and_offline(self):
        with tempfile.TemporaryDirectory() as directory:
            guard = Mock()
            guard.fetch.side_effect = [json.dumps([{'lat': '52.5', 'lon': '13.4'}]),
                                       json.dumps({'itineraries': [{'duration': 1800}]})]
            client = Commute(guard, directory)
            match = client.geocode('Fictional public square Berlin')
            self.assertEqual(match['latitude'], 52.5)
            at = datetime(2026, 1, 1, tzinfo=timezone.utc)
            result = client.route([52.5, 13.4], [52.51, 13.41], at=at)
            self.assertEqual(result['minutes'], 30)
            client.offline = True
            self.assertEqual(client.geocode('Fictional public square Berlin'), match)
            self.assertEqual(client.route([52.5, 13.4], [52.51, 13.41], at=at), result)
            self.assertEqual(guard.fetch.call_count, 2)
            self.assertIn('github.com', guard.fetch.call_args.kwargs['headers']['User-Agent'])
            self.assertEqual(client.geocode('another place')['status'], 'unknown')

    def test_failures_and_invalid_inputs_are_unknown(self):
        with tempfile.TemporaryDirectory() as directory:
            guard = Mock()
            client = Commute(guard, directory)
            for failure in (SourceError('offline'), Blocked('challenge'), Deferred('budget'), OSError('disk')):
                guard.fetch.side_effect = failure
                self.assertEqual(client.geocode('fictional')['status'], 'unknown')
                self.assertEqual(client.route([52, 13], [53, 14])['status'], 'unknown')
            guard.fetch.side_effect = None
            for body in ('[]', '{}', 'null', 'not JSON'):
                guard.fetch.return_value = body
                self.assertEqual(client.geocode('fictional ' + body)['status'], 'unknown')
                self.assertEqual(client.route([52, 13], [53, 14])['status'], 'unknown')
            self.assertEqual(client.geocode('')['status'], 'unknown')
            self.assertEqual(client.route(None, [53, 14])['status'], 'unknown')
            self.assertEqual(client.route([92, 13], [53, 14])['status'], 'unknown')
            with self.assertRaises(ValueError):
                coordinates([True, 13])

    def test_nominatim_minimum_gap_persisted_and_shared(self):
        with tempfile.TemporaryDirectory() as directory:
            sleep = Mock()
            guard = Guard(directory, clock=lambda: 1000, sleep=sleep, jitter=lambda: 0)
            guard.reserve('nominatim')
            Guard(directory, clock=lambda: 1000, sleep=sleep, jitter=lambda: 0).reserve('nominatim')
            sleep.assert_called_once_with(1)

    def test_cli_offline(self):
        with tempfile.TemporaryDirectory() as directory, patch('commute.Guard'), patch('sys.stdout', io.StringIO()) as out:
            with patch('commute.Commute.cached', side_effect=SourceError('offline')):
                self.assertEqual(commute_main(['--origin', 'fictional', '--to-coordinates', '52', '13', '--offline']), 1)
            self.assertEqual(json.loads(out.getvalue())['route']['status'], 'unknown')
