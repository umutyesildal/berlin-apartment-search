import io
import json
import tempfile
from pathlib import Path
from unittest.mock import patch
from support import ROOT, OfflineTest, fixture, working_directory
from alerts import main as alerts_main, parse as parse_email
from import_page import build_report, main as page_main, parse_html, parse_text


FIXTURES = ROOT / 'tests' / 'fixtures'


class ImportTests(OfflineTest):
    def test_detail_main_is_independent_of_recommendations_and_fragment_links(self):
        url = 'https://www.immowelt.de/expose/fictional-main'
        for suffix in ('', '<a href="#contact">Contact</a>',
                       '<section class="recommendations"><article><h2>Other flat</h2>'
                       '<a href="/expose/fictional-other">View</a><p>1500 € Warmmiete; 90 m²; 4 Zimmer</p></article></section>'):
            with self.subTest(suffix=suffix):
                text = '<main><h1>Main fictional flat</h1><p>Warmmiete: 900 €; 50 m²; 2 Zimmer</p>' + suffix + '</main>'
                rows = {row.source_id: row for row in parse_html(text, url)}
                self.assertIn('fictional-main', rows)
                main = rows['fictional-main']
                self.assertEqual((main.title, main.warm_eur, main.area_m2, main.rooms), ('Main fictional flat', 900, 50, 2))
                if 'fictional-other' in suffix:
                    other = rows['fictional-other']
                    self.assertEqual((other.warm_eur, other.area_m2, other.rooms), (1500, 90, 4))
                else:
                    self.assertEqual(len(rows), 1)

    def test_rent_labels_stay_on_their_line_and_prefer_amount_before_label(self):
        url = 'https://www.immowelt.de/expose/fictional-rent'
        for text in ('700 € Kaltmiete\n900 € Warmmiete', '700 € Kaltmiete\r\n900 € Warmmiete',
                     '700 € Kaltmiete 900 € Warmmiete', 'Kaltmiete: 700 €\nWarmmiete: 900 €'):
            with self.subTest(text=text):
                row = parse_text(text, url)[0]
                self.assertEqual((row.cold_eur, row.warm_eur), (700, 900))
        row = parse_text('Kaltmiete\n900 €', url)[0]
        self.assertIsNone(row.cold_eur)
        self.assertEqual(row.asking_eur, 900)

    def test_mime_alternatives_and_multiple_portals(self):
        for name, source, price_field, expected in (
                ('alert_immowelt.eml', 'immowelt', 'warm_eur', 900),
                ('alert_mobile.eml', 'immoscout', 'cold_eur', 700),
                ('alert_kleinanzeigen.eml', 'kleinanzeigen', 'asking_eur', 850)):
            rows = parse_email((FIXTURES / name).read_bytes())
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0].source, source)
            self.assertEqual(getattr(rows[0], price_field), expected)
            self.assertEqual(rows[0].rooms, 2)
            self.assertEqual(rows[0].posted_at, '')

    def test_jsonld_page_and_untrusted_text_assessments(self):
        rows = parse_html(fixture('saved_page.html'))
        self.assertEqual(len(rows), 1)
        self.assertEqual((rows[0].area_m2, rows[0].rooms, rows[0].asking_eur), (60, 2, 950))
        member = build_report(rows, 'offline')['groups'][0]['members'][0]
        self.assertTrue(member['integrity']['needs_review'])
        self.assertIsNone(rows[0].warm_eur)
        card = '<article><a href="/expose/fictional-102">Fictional flat</a>Warmmiete: 1000 EUR; 60 m²</article>'
        self.assertEqual(parse_html(card, 'https://www.immowelt.de/')[0].warm_eur, 1000)

    def test_plain_paste_and_no_shared_price_for_multi_link_block(self):
        rows = parse_text('Fictional flat\nKaltmiete: 700 EUR; 2 Zimmer; 50 m2',
                          'https://www.immowelt.de/expose/fictional-103')
        self.assertEqual(rows[0].cold_eur, 700)
        rows = parse_text('900 EUR https://www.immowelt.de/expose/fictional-104 https://www.immowelt.de/expose/fictional-105')
        self.assertEqual(len(rows), 2)
        self.assertTrue(all(row.asking_eur is None for row in rows))

    def test_empty_invalid_and_attachment_only_do_not_invent_entries(self):
        self.assertEqual(parse_email(b''), [])
        self.assertEqual(parse_html('<html>CAPTCHA required</html>'), [])
        self.assertEqual(parse_html('<title>Access denied</title><h1>Verify you are human</h1>',
                                    'https://www.immowelt.de/expose/fictional-106'), [])
        self.assertEqual(parse_html('', 'https://www.immowelt.de/expose/fictional-106'), [])
        self.assertEqual(parse_html('<h1>Verify you are human</h1><a href="#challenge">Continue</a>',
                                    'https://www.immowelt.de/expose/fictional-106'), [])
        self.assertEqual(parse_html('<script type="application/ld+json">broken json</script>'), [])
        self.assertEqual(parse_text('https://www.immowelt.de/privacy'), [])
        email = b'Content-Type: text/plain\nContent-Disposition: attachment\n\nhttps://www.immowelt.de/expose/fictional-106'
        self.assertEqual(parse_email(email), [])
        with self.assertRaises(ValueError):
            parse_email('not bytes')

    def test_cli_outputs_private_reports_and_handles_errors(self):
        with tempfile.TemporaryDirectory() as directory, working_directory(directory), patch('sys.stdout', io.StringIO()):
            self.assertEqual(alerts_main([str(FIXTURES / 'alert_immowelt.eml')]), 0)
            self.assertEqual(page_main([str(FIXTURES / 'saved_page.html')]), 0)
            self.assertTrue(Path('flat-search/alerts/results.json').is_file())
            self.assertTrue(Path('flat-search/imported-page/shortlist.html').is_file())
            empty = Path('flat-search/empty.html')
            empty.write_text('', encoding='utf-8')
            self.assertEqual(page_main([str(empty)]), 1)
            for main in (alerts_main, page_main):
                with patch('sys.stderr', io.StringIO()), self.assertRaises(SystemExit):
                    main(['missing-file'])
