import io
import json
import tempfile
from pathlib import Path
from unittest.mock import patch
from support import ROOT, OfflineTest, fixture, working_directory
from alerts import main as alerts_main, parse as parse_email
from import_page import build_report, main as page_main, parse_html, parse_text, visible_text
from sources.html_tools import Document


FIXTURES = ROOT / 'tests' / 'fixtures'


class ImportTests(OfflineTest):
    def test_source_whitespace_does_not_change_table_rents(self):
        url = 'https://www.immowelt.de/expose/fictional-whitespace'
        for name in ('saved_rent_table.html', 'saved_rent_table_amount_first.html', 'saved_rent_dl.html'):
            compact = fixture(name).replace('\n', '')
            formatted = compact.replace('><', '>\n  <')
            formatted = formatted.replace('Kaltmiete', '\n Kaltmiete\n ').replace('Warmmiete', '\n Warmmiete\n ')
            formatted = formatted.replace('700 €', '700\n €').replace('900 €', '900\t €')
            with self.subTest(fixture=name):
                for html in (compact, formatted):
                    row = parse_html(html, url)[0]
                    self.assertEqual((row.cold_eur, row.warm_eur), (700, 900))

    def test_rent_amounts_are_claimed_once_in_label_order(self):
        url = 'https://www.immowelt.de/expose/fictional-pairs'
        for text, expected in [
                ('Kaltmiete 700 € Warmmiete 900 €', (700, 900)),
                ('700 € Kaltmiete 900 € Warmmiete', (700, 900)),
                ('Warmmiete: 900 EUR; Kaltmiete: 700 EUR', (700, 900)),
                ('700 € Kaltmiete Warmmiete 900 €', (700, 900)),
                ('Kaltmiete 700 € Warmmiete', (700, None)),
                ('700 € Kaltmiete Warmmiete', (700, None)),
                ('Kaltmiete Warmmiete 900 €', (None, 900))]:
            with self.subTest(text=text):
                row = parse_text(text, url)[0]
                self.assertEqual((row.cold_eur, row.warm_eur), expected)

    def test_nested_table_and_cell_paragraph_boundaries(self):
        url = 'https://www.immowelt.de/expose/fictional-nested'
        for fields in (
                '<table><tr><td><table><tr><td>Kaltmiete</td><td>700 €</td></tr>'
                '<tr><td>Warmmiete</td><td>900 €</td></tr></table></td></tr></table>',
                '<table><tr><td><p>Kaltmiete 700 €</p><p>Warmmiete 900 €</p></td></tr></table>',
                '<table><tr><td>Kaltmiete</td><td>700 €</td><td>Warmmiete</td><td>900 €</td></tr></table>'):
            html = '<main><h1>Flat</h1>' + fields + '</main>'
            with self.subTest(fields=fields):
                row = parse_html(html, url)[0]
                self.assertEqual((row.cold_eur, row.warm_eur), (700, 900))
        paragraphs = Document('<table><tr><td><p>Kaltmiete 700 €</p><p>Warmmiete 900 €</p></td></tr></table>')
        self.assertIn('700 €\nWarmmiete', visible_text(paragraphs.root, set()))

    def test_html_rent_fields_keep_block_boundaries(self):
        url = 'https://www.immowelt.de/expose/fictional-fields'
        for name in ('saved_rent_dl.html', 'saved_rent_table.html', 'saved_rent_table_amount_first.html'):
            with self.subTest(fixture=name):
                row = parse_html(fixture(name), url)[0]
                self.assertEqual((row.cold_eur, row.warm_eur), (700, 900))
        for cells in ('<td><p>700 €</p></td><th><div>Kaltmiete</div></th>',
                      '<th><p>Kaltmiete</p></th><td><div>700 €</div></td>'):
            html = '<main><h1>Flat</h1><table><tr>' + cells + '</tr>\n<tr><td>900 €</td><th>Warmmiete</th></tr></table></main>'
            with self.subTest(cells=cells):
                row = parse_html(html, url)[0]
                self.assertEqual((row.cold_eur, row.warm_eur), (700, 900))
        for fields in ('<div>Kaltmiete:</div><div>700 €</div><div>Warmmiete:</div><div>900 €</div>',
                       '<p>Kaltmiete:<br>700 €</p><p>Warmmiete:<br>900 €</p>',
                       '<ul><li>700 € Kaltmiete</li><li>900 € Warmmiete</li></ul>'):
            with self.subTest(fields=fields):
                row = parse_html('<main><h1>Flat</h1>' + fields + '</main>', url)[0]
                self.assertEqual((row.cold_eur, row.warm_eur), (700, 900))
        row = parse_html('<main><h1>Flat</h1><dl><dt>Kaltmiete</dt><dd></dd>'
                         '<dt>Warmmiete</dt><dd>900 €</dd></dl></main>', url)[0]
        self.assertIsNone(row.cold_eur)
        self.assertEqual(row.warm_eur, 900)

    def test_html_alert_keeps_supported_links_without_facts_but_saved_shell_does_not(self):
        html = ('<p><a href="https://www.immowelt.de/expose/fictional-alert">View offer</a></p>'
                '<p><a href="https://www.immobilienscout24.de/expose/123456">Other offer</a></p>'
                '<a href="https://www.immowelt.de/privacy">Privacy</a>')
        message = ('MIME-Version: 1.0\nContent-Type: text/html; charset=utf-8\n\n' + html).encode('utf-8')
        rows = parse_email(message)
        self.assertEqual({row.source for row in rows}, {'immowelt', 'immoscout'})
        self.assertTrue(all(row.area_m2 is None and row.rooms is None and row.asking_eur is None for row in rows))
        self.assertEqual(parse_html(html), [])
        self.assertEqual(parse_email(b'Content-Type: text/html\n\n<p>No offers</p>'), [])

    def test_canonical_page_identity_keeps_details_with_next_listing_navigation(self):
        primary = 'https://www.immowelt.de/expose/fictional-main'
        for metadata, saved_url in [('', primary), ('<link rel="canonical" href="' + primary + '">', ''),
                                    ('<meta property="og:url" content="' + primary + '">', '')]:
            for relation in ('', ' rel="next"'):
                with self.subTest(metadata=metadata, relation=relation):
                    text = ('<html><head>' + metadata + '</head><body><h1>Main flat</h1>'
                            '<section><p>Warmmiete: 900 €; 50 m²; 2 Zimmer</p>'
                            '<a href="https://www.immowelt.de/expose/fictional-next"' + relation + '>Next listing</a>'
                            '</section></body></html>')
                    rows = parse_html(text, saved_url)
                    self.assertEqual(len(rows), 1)
                    self.assertEqual((rows[0].source_id, rows[0].warm_eur, rows[0].area_m2, rows[0].rooms),
                                     ('fictional-main', 900, 50, 2))

    def test_nested_unrecognized_recommendation_cannot_fill_main_facts(self):
        text = ('<main><h1>Main flat</h1><p>50 m²</p><div class="unknown-widget">'
                '<p><a href="/expose/fictional-other">Other flat</a></p>'
                '<div><span>Warmmiete: 1500 €; 4 Zimmer; 90 m²</span></div></div></main>')
        rows = {row.source_id: row for row in parse_html(text, 'https://www.immowelt.de/expose/fictional-main')}
        self.assertEqual(rows['fictional-main'].area_m2, 50)
        self.assertIsNone(rows['fictional-main'].warm_eur)
        self.assertIsNone(rows['fictional-main'].rooms)
        self.assertEqual(rows['fictional-other'].warm_eur, 1500)

    def test_html_shell_without_listing_facts_is_not_imported_and_cli_explains(self):
        url = 'https://www.immowelt.de/expose/fictional-shell'
        for html in ('<title>Fictional apartment</title><script>loadListing()</script>',
                     '<h1>Fictional apartment</h1><div id="app"></div>',
                     '<script type="application/ld+json">' + json.dumps({'@type': 'Apartment', 'url': url, 'name': 'Flat'}) + '</script>'):
            with self.subTest(html=html):
                self.assertEqual(parse_html(html, url), [])
        for fact in ('Warmmiete: 900 €', '50 m²', '2 Zimmer', '10115 Berlin'):
            self.assertEqual(len(parse_html('<h1>Flat</h1><p>' + fact + '</p>', url)), 1)
        with tempfile.TemporaryDirectory() as directory, working_directory(directory), patch('sys.stdout', io.StringIO()) as output:
            Path('shell.html').write_text('<title>Flat</title><script>load()</script>', encoding='utf-8')
            self.assertEqual(page_main(['shell.html', '--url', url]), 1)
            self.assertIn('no_listing_found', output.getvalue())
            self.assertIn('fully loaded page', output.getvalue())

    def test_unrecognized_recommendation_wrapper_does_not_supply_main_facts(self):
        url = 'https://www.immowelt.de/expose/fictional-main'
        for tag in ('div', 'section', 'p'):
            html = ('<main><h1>Main flat</h1><p>50 m²</p><' + tag + ' class="widget-xyz">'
                    '<span><a href="/expose/fictional-other">Other flat</a></span>'
                    '<span>Warmmiete: 1500 €; 4 Zimmer; 90 m²</span></' + tag + '></main>')
            with self.subTest(tag=tag):
                rows = {row.source_id: row for row in parse_html(html, url)}
                self.assertIsNone(rows['fictional-main'].warm_eur)
                self.assertIsNone(rows['fictional-main'].rooms)
                self.assertEqual(rows['fictional-main'].area_m2, 50)
                self.assertEqual((rows['fictional-other'].warm_eur, rows['fictional-other'].rooms), (1500, 4))

    def test_colon_only_rent_label_accepts_only_its_immediate_unlabelled_amount_line(self):
        url = 'https://www.immowelt.de/expose/fictional-lines'
        for text, expected in [('Warmmiete:\n900 €', (None, 900)),
                               (' Warmmiete: \r\n 900 EUR', (None, 900)),
                               ('Kaltmiete:\n900 € Warmmiete', (None, 900)),
                               ('Warmmiete:\n700 € Kaltmiete', (700, None)),
                               ('Warmmiete\n900 €', (None, None)),
                               ('Warmmiete: extra\n900 €', (None, None)),
                               ('Warmmiete:\n\n900 €', (None, None)),
                               ('700 € Kaltmiete\n900 € Warmmiete', (700, 900))]:
            with self.subTest(text=text):
                row = parse_text(text, url)[0]
                self.assertEqual((row.cold_eur, row.warm_eur), expected)

    def test_partial_jsonld_preserves_description_facts_unless_structured_value_is_known(self):
        base = {'@type': 'Apartment', 'url': 'https://www.immowelt.de/expose/fictional-partial',
                'name': 'Fictional flat', 'description': '50 m²; 2 Zimmer; 900 EUR; 10115 Berlin'}
        for partial in ({}, {'floorSize': None, 'numberOfRooms': None, 'offers': {}},
                        {'floorSize': {'value': ''}, 'numberOfRooms': {'value': ''},
                         'offers': {'price': None}, 'address': {'postalCode': ''}}):
            with self.subTest(partial=partial):
                html = '<script type="application/ld+json">' + json.dumps(dict(base, **partial)) + '</script>'
                row = parse_html(html)[0]
                self.assertEqual((row.area_m2, row.rooms, row.asking_eur, row.postcode), (50, 2, 900, '10115'))
        data = dict(base, floorSize={'value': 60, 'unitCode': 'MTK'}, numberOfRooms=3,
                    offers={'price': 1000, 'priceCurrency': 'EUR'})
        row = parse_html('<script type="application/ld+json">' + json.dumps(data) + '</script>')[0]
        self.assertEqual((row.area_m2, row.rooms, row.asking_eur), (60, 3, 1000))

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
