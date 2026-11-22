import json
from unittest.mock import Mock
from support import OfflineTest, fixture
from guard import Blocked, SourceError
from sources import inberlinwohnen, immoscout, kleinanzeigen
from sources.html_tools import Document


class SourceTests(OfflineTest):
    def test_livewire_nested_markers(self):
        rows = inberlinwohnen.parse(fixture('inberlinwohnen.html'))
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row.id, 'inberlinwohnen:fiction-101')
        self.assertEqual((row.cold_eur, row.warm_eur, row.area_m2), (700, 910, 60.5))
        self.assertFalse(row.wbs)
        self.assertEqual(row.street, 'Fiktivweg 99')
        self.assertEqual(row.latitude, 52.5)

    def test_mobile_cards_and_ambiguous_price(self):
        row, = immoscout.parse(fixture('immoscout.json'))
        self.assertEqual((row.rooms, row.area_m2, row.asking_eur), (2, 60.5, 830))
        self.assertIsNone(row.cold_eur)
        self.assertIsNone(row.warm_eur)
        self.assertEqual(row.postcode, '10000')

    def test_mobile_explicit_rent_basis(self):
        data = json.loads(fixture('immoscout.json'))
        data['resultListItems'][1]['item']['attributes'][0]['label'] = 'Warmmiete'
        row, = immoscout.parse(json.dumps(data))
        self.assertEqual(row.warm_eur, 830)

    def test_html_old_and_new_cards(self):
        rows = kleinanzeigen.parse(fixture('kleinanzeigen.html'))
        self.assertEqual(len(rows), 2)
        self.assertEqual((rows[0].asking_eur, rows[0].area_m2, rows[0].rooms), (950, 60, 2))
        self.assertEqual(rows[0].postcode, '10000')
        self.assertEqual(rows[1].asking_eur, 1200)
        self.assertIsNone(rows[0].warm_eur)

    def test_jsonld_fallback(self):
        text = fixture('kleinanzeigen.html').replace('<h3>', '<div>').replace('</h3>', '</div>')
        self.assertEqual(kleinanzeigen.parse(text)[0].title, 'Fiktives Zuhause')

    def test_explicit_empty_sources(self):
        for module, name in ((inberlinwohnen, 'inberlinwohnen-empty.html'),
                             (immoscout, 'immoscout-empty.json'), (kleinanzeigen, 'kleinanzeigen-empty.html')):
            with self.subTest(source=module.NAME):
                self.assertEqual(module.parse(fixture(name)), [])

    def test_blocks_and_drift_not_empty(self):
        for module in (inberlinwohnen, immoscout, kleinanzeigen):
            for text in ('', '<html>Unexpected content</html>', fixture('blocked.html')):
                with self.subTest(source=module.NAME, text=text[:20]):
                    with self.assertRaises(Blocked):
                        module.parse(text)

    def test_malformed_recognized_shapes(self):
        cases = ((inberlinwohnen, '<div wire:snapshot="bad"></div>'),
                 (immoscout, '{"resultListItems":[{"type":"EXPOSE_RESULT","item":{}}]}'),
                 (kleinanzeigen, '<article data-adid="fiction"></article>'))
        for module, text in cases:
            with self.subTest(source=module.NAME), self.assertRaises(SourceError):
                module.parse(text)

    def test_each_adapter_uses_one_guarded_request(self):
        for module, name in ((inberlinwohnen, 'inberlinwohnen.html'),
                             (immoscout, 'immoscout.json'), (kleinanzeigen, 'kleinanzeigen.html')):
            guard = Mock()
            guard.fetch.return_value = fixture(name)
            self.assertTrue(module.search(guard, max_warm=1200, min_rooms=2))
            guard.fetch.assert_called_once()
            if module is immoscout:
                args = guard.fetch.call_args.args
                self.assertIn('pricetype=calculatedtotalrent', args[1])
                self.assertEqual(json.loads(args[3]), {'supportedResultListTypes': [], 'userData': {}})

    def test_html_tree_void_and_mismatched_tags(self):
        doc = Document('<article><img src="x"/><p>A<br>B</p></article><p>C</p>')
        self.assertEqual(doc.root.text(), 'A B C')
