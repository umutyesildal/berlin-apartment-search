"""Offline saved HTML/text import. Never fetches URLs, scripts, cookies or assets."""

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit
from dedupe import group
from models import Listing, digest, normalize, safe_url
from search import enrich, write_report
from sources.html_tools import Document


MAX_BYTES = 5 * 1024 * 1024
PORTALS = {'immowelt.de': ('immowelt', r'/expose/([^/]+)'),
           'immobilienscout24.de': ('immoscout', r'/expose/([^/]+)'),
           'kleinanzeigen.de': ('kleinanzeigen', r'/s-anzeige/[^/]+/(\d+)(?:-[^/]*)?'),
           'immobilien.de': ('immobiliende', r'/wohnen/(.+)'),
           'wg-gesucht.de': ('wggesucht', r'/[^/]+\.(\d+)\.html'),
           'wunderflats.com': ('wunderflats', r'/en/furnished-apartment/[^/]+/([^/]+)'),
           'deutsche-wohnen.com': ('deutschewohnen', r'/expose/([^/]+)'),
           'housinganywhere.com': ('housinganywhere', r'/room/([^/]+)(?:/.*)?'),
           'ohne-makler.net': ('ohnemakler', r'/immobilie[n]?/(\d+)')}


def identity(url, allow_unknown=False):
    if not safe_url(url):
        return None
    parsed = urlsplit(url)
    host = parsed.hostname.removeprefix('www.')
    query = [(key, value) for key, value in parse_qsl(parsed.query, keep_blank_values=True)
             if not key.casefold().startswith('utm_') and key.casefold() not in ('fbclid', 'gclid')]
    clean = urlunsplit(('https', parsed.netloc, parsed.path.rstrip('/'), urlencode(sorted(query)), ''))
    if host in PORTALS:
        source, pattern = PORTALS[host]
        match = re.fullmatch(pattern, parsed.path.rstrip('/'))
        if match:
            return source, match.group(1), clean
    return (host, digest([clean]), clean) if allow_unknown else None


def from_text(text, url, title='', allow_unknown=False):
    found = identity(url, allow_unknown)
    if not found:
        return None
    source, identifier, url = found
    text = text[:40000]
    listing = Listing(source, identifier, url, title[:500] or 'Imported offer', text=text)
    amount = r'([\d][\d.,\u00a0 ]*)\s*(?:€|EUR)'
    labels = {'cold_eur': 'Kaltmiete|Nettokaltmiete', 'warm_eur': 'Warmmiete|Gesamtmiete',
              'costs_eur': 'Nebenkosten|Betriebskosten', 'deposit_eur': 'Kaution'}
    for field, label in labels.items():
        match = re.search(r'(?:' + label + r')\s*:?\s*' + amount, text, re.I)
        if not match:
            match = re.search(amount + r'\s*(?:' + label + r')\b', text, re.I)
        if match:
            setattr(listing, field, match.group(1))
    if not any(getattr(listing, field) is not None for field in labels):
        prices = re.findall(amount, text, re.I)
        if len(prices) == 1:
            listing.asking_eur = prices[0]
    for field, pattern in (('area_m2', r'(\d+(?:[.,]\d+)?)\s*(?:m²|m2)\b'),
                           ('rooms', r'(\d+(?:[.,]\d+)?)\s*(?:Zimmer|Zi\.?)\b')):
        match = re.search(pattern, text, re.I)
        if match:
            setattr(listing, field, match.group(1))
    match = re.search(r'\b(\d{5})\b', text)
    if match:
        listing.postcode = match.group(1)
    return normalize(listing)


def merge(rows):
    output = {}
    for row in rows:
        if row.id not in output:
            output[row.id] = row
            continue
        previous = output[row.id]
        for key, value in vars(row).items():
            if key == 'text':
                previous.text = (previous.text + '\n' + value)[:40000]
            elif getattr(previous, key) in ('', None) and value not in ('', None):
                setattr(previous, key, value)
    return list(output.values())


def objects(value):
    if isinstance(value, list):
        for item in value:
            yield from objects(item)
    elif isinstance(value, dict):
        yield value
        for item in value.values():
            if isinstance(item, (list, dict)):
                yield from objects(item)


def quantity(value):
    return value.get('value') if isinstance(value, dict) else value


def parse_html(text, base_url=''):
    if re.search(r'<title>[^<]*(?:captcha|access denied|just a moment|robot|zugriff verweigert)', text, re.I):
        return []
    root, rows = Document(text).root, []
    structured = []
    for node in root.walk():
        if node.tag != 'script' or node.attrs.get('type') != 'application/ld+json':
            continue
        try:
            for item in objects(json.loads(node.text(scripts=True))):
                types = item.get('@type', [])
                types = [types] if isinstance(types, str) else types
                if isinstance(types, list) and set(types).intersection(('Apartment', 'House', 'Residence', 'RealEstateListing', 'Accommodation')):
                    structured.append(item)
        except ValueError:
            continue
    for item in structured:
        link = item.get('url') or item.get('@id') or (base_url if len(structured) == 1 else '')
        if not isinstance(link, str):
            continue
        link = urljoin(base_url, link)
        title = str(item.get('name') or item.get('headline') or 'Imported offer')
        row = from_text(str(item.get('description') or ''), link, title, allow_unknown=True)
        if row is None:
            continue
        address = item.get('address')
        if isinstance(address, dict):
            row.street, row.postcode = address.get('streetAddress', ''), address.get('postalCode', '')
        size = item.get('floorSize')
        if not isinstance(size, dict) or size.get('unitCode', size.get('unitText', 'MTK')) in ('MTK', 'm2', 'm²'):
            row.area_m2 = quantity(size)
        row.rooms = quantity(item.get('numberOfRooms'))
        offer = item.get('offers')
        if isinstance(offer, dict) and offer.get('priceCurrency', 'EUR') == 'EUR':
            row.asking_eur = offer.get('price')
        row.posted_at = item.get('datePosted') or item.get('datePublished') or ''
        rows.append(normalize(row))
    for node in root.walk():
        card = node.tag in ('article', 'li', 'tr') or (node.tag == 'div' and re.search(
            r'card|listing|expose|offer', node.attrs.get('class', ''), re.I))
        if not card:
            continue
        links = {}
        for child in node.walk():
            if child.tag == 'a':
                link = urljoin(base_url, child.attrs.get('href', ''))
                found = identity(link)
                if found:
                    links[found[:2]] = (link, child.text())
        if len(links) == 1:
            link, title = next(iter(links.values()))
            heading = next((child.text() for child in node.walk() if child.tag in ('h1', 'h2', 'h3')), '')
            rows.append(from_text(node.text(), link, heading or title))
    for node in root.walk():
        if node.tag == 'a':
            row = from_text(node.text(), urljoin(base_url, node.attrs.get('href', '')), node.text())
            if row:
                rows.append(row)
    if not rows and identity(base_url):
        heading = next((node.text() for node in root.walk() if node.tag == 'h1'), '')
        if heading and not re.search(r'captcha|access denied|verify you are human|kein roboter', heading, re.I):
            rows.append(from_text(root.text(), base_url, heading))
    return merge(rows)


def parse_text(text, base_url=''):
    if base_url:
        row = from_text(text, base_url, next(iter(text.splitlines()), 'Imported offer'), allow_unknown=True)
        return [row] if row else []
    rows = []
    for block in re.split(r'\n\s*\n', text):
        links = [link.rstrip('.,;)') for link in re.findall(r'https://[^\s<>"\x27]+', block)]
        links = list(dict.fromkeys(link for link in links if identity(link)))
        for link in links:
            context = block if len(links) == 1 else link
            row = from_text(context, link, context.splitlines()[0])
            if row:
                rows.append(row)
    return merge(rows)


def build_report(rows, origin):
    return enrich({'generated_at': datetime.now(timezone.utc).isoformat(),
                   'sources': {origin: {'status': 'ok' if rows else 'unsupported', 'returned': len(rows),
                                        'kept': len(rows), 'blocked': None,
                                        'reason': 'Offline import; not portal inventory or sender verification.'}},
                   'listing_count': len(rows), 'groups': group(rows)})


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('page', type=Path)
    parser.add_argument('--url', default='', help='Original HTTPS page URL; never fetched')
    parser.add_argument('--text', action='store_true', help='Input is pasted plain text rather than HTML')
    args = parser.parse_args(argv)
    try:
        if args.page.stat().st_size > MAX_BYTES or (args.url and not safe_url(args.url)):
            raise ValueError('input exceeds 5 MiB or original URL is not safe HTTPS')
        text = args.page.read_text(encoding='utf-8', errors='replace')
        rows = parse_text(text, args.url) if args.text else parse_html(text, args.url)
        write_report(build_report(rows, 'saved_page'), Path('flat-search/imported-page'))
        print(json.dumps({'listing_count': len(rows), 'status': 'imported' if rows else 'unrecognized',
                          'output': 'flat-search/imported-page/results.json'}))
        return 0 if rows else 1
    except (OSError, ValueError, TypeError, RecursionError):
        parser.error('Saved page could not be imported; no URLs or private input contents logged.')


if __name__ == '__main__':
    raise SystemExit(main())
