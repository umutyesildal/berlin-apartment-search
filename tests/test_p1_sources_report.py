import json
import tempfile
from pathlib import Path
from unittest.mock import Mock
from support import OfflineTest, fixture
from guard import Blocked, SourceError
from report import render, write
from sources import wggesucht, wunderflats


class NewSourceTests(OfflineTest):
    def test_normalized_cards_and_guarded_requests(self):
        for adapter in (wggesucht, wunderflats):
            with self.subTest(source=adapter.NAME):
                guard = Mock()
                guard.fetch.return_value = fixture(adapter.NAME + '.html')
                rows = adapter.search(guard)
                guard.fetch.assert_called_once_with(adapter.NAME, adapter.URL)
                self.assertEqual(len(rows), 1)
                self.assertTrue(rows[0].url.startswith('https://'))
        wg = wggesucht.parse(fixture('wggesucht.html'))[0]
        self.assertEqual((wg.warm_eur, wg.area_m2, wg.source_id), (700, 20, '101'))
        wf = wunderflats.parse(fixture('wunderflats.html'))[0]
        self.assertEqual((wf.asking_eur, wf.area_m2, wf.rooms), (1250, 45, 2))
        self.assertIsNone(wf.warm_eur)
        self.assertNotIn('tracking=', wf.url)

    def test_explicit_empty_errors_and_blocks(self):
        for adapter, empty in ((wggesucht, 'Keine Angebote gefunden'), (wunderflats, 'No apartments found')):
            self.assertEqual(adapter.parse('<html>' + empty + '</html>'), [])
            with self.assertRaises(Blocked):
                adapter.parse('<html>unrecognized challenge</html>')
        with self.assertRaises(SourceError):
            wggesucht.parse('<div class="offer_list_item">Broken card</div>')
        with self.assertRaises(SourceError):
            wunderflats.parse('<article class="Listing">Broken card</article>')
        with self.assertRaises(SourceError):
            wunderflats.parse('<script type="application/ld+json">bad</script>')


class ReportTests(OfflineTest):
    def test_escape_flags_duplicates_links_and_write(self):
        member = {'title': '<script>alert(1)</script>[bad](url)', 'url': 'https://example.test/a?q="<bad>',
                  'fit': {'score': 75}, 'scam': {'review': '<img src=x>'}, 'rent': {'costs_review': True}}
        data = {'sources': {'fictional': {'status': 'error'}}, 'groups': [{'possible_duplicate': True, 'members': [member]}]}
        markdown, page = render(data)
        self.assertNotIn('<script>', page)
        self.assertNotIn('<img', page)
        self.assertIn('&lt;script&gt;', page)
        self.assertIn('Possible duplicate: True', page)
        self.assertIn('75 / 100', page)
        self.assertIn('costs_review', page)
        self.assertIn('%22%3Cbad%3E', page)
        self.assertNotIn('[bad](url)', markdown)
        with tempfile.TemporaryDirectory() as directory:
            write(data, directory)
            self.assertEqual((Path(directory) / 'shortlist.html').read_text(), page)
        member['url'] = 'javascript:alert(1)'
        self.assertNotIn('href=', render(data)[1])

    def test_empty_and_invalid(self):
        self.assertIn('No shortlist entries', render({'groups': []})[0])
        with self.assertRaises(KeyError):
            render({})
