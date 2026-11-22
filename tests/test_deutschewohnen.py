import json
from unittest.mock import Mock
from support import OfflineTest, fixture
from guard import Blocked, SourceError
from sources import deutschewohnen as source


class DeutscheWohnenTests(OfflineTest):
    def test_guarded_public_token_flow_and_normalized_fields(self):
        guard = Mock()
        guard.fetch.side_effect = ['{"token":"fictional-public-search-token"}', fixture('deutschewohnen.json')]
        rows = source.search(guard)
        self.assertEqual(guard.fetch.call_count, 2)
        self.assertEqual(guard.fetch.call_args_list[0].args, ('deutschewohnen', source.TOKEN_URL))
        self.assertEqual(guard.fetch.call_args.kwargs['headers']['X-VON-Search-Token'], 'fictional-public-search-token')
        self.assertNotIn('token', source.LIST_URL)
        row = rows[0]
        self.assertEqual((row.cold_eur, row.warm_eur, row.asking_eur, row.area_m2, row.rooms), (None, None, 900, 50, 2))
        self.assertEqual((row.latitude, row.longitude), (52.5, 13.4))
        self.assertEqual(row.postcode, '10115')

    def test_empty_unknown_and_schema_drift_are_distinct(self):
        self.assertEqual(source.parse({'results': []}), [])
        with self.assertRaises(Blocked):
            source.parse({'challenge': True})
        for result in ([None], [{}]):
            with self.assertRaises(SourceError):
                source.parse({'results': result})
        row = source.parse({'results': [{'wrk_id': 'fiction-2', 'titel': 'Unknown prices', 'slug': '../unsafe', 'lat': 0, 'lng': 0}]})[0]
        self.assertIsNone(row.warm_eur)
        self.assertEqual(row.url, '')
        self.assertIsNone(row.latitude)

    def test_missing_token_block_and_bad_json_do_not_retry(self):
        for response in ('{}', 'null', '{"token":0}', 'not json'):
            guard = Mock()
            guard.fetch.return_value = response
            with self.assertRaises(Blocked if response == 'not json' else SourceError):
                source.search(guard)
            guard.fetch.assert_called_once()
        guard = Mock()
        guard.fetch.side_effect = Blocked('challenge')
        with self.assertRaises(Blocked):
            source.search(guard)
        guard.fetch.assert_called_once()
