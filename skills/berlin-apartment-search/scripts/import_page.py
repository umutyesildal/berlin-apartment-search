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
NO_LISTING = 'No listing found. Save the fully loaded page with listing details and try again.'
PORTALS = {'immowelt.de': ('immowelt', r'/expose/([^/]+)'),
           'immobilienscout24.de': ('immoscout', r'/expose/([^/]+)'),
           'kleinanzeigen.de': ('kleinanzeigen', r'/s-anzeige/[^/]+/(\d+)(?:-[^/]*)?'),
           'immobilien.de': ('immobiliende', r'/wohnen/(.+)'),
           'wg-gesucht.de': ('wggesucht', r'/[^/]+\.(\d+)\.html'),
           'wunderflats.com': ('wunderflats', r'/en/furnished-apartment/[^/]+/([^/]+)'),
           'deutsche-wohnen.com': ('deutschewohnen', r'/mieten/mietangebote/([^/]+)'),
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
    gap = r'[ \t\u00a0]*'
    amount = r'([\d][\d.,\u00a0 ]*)' + gap + r'(?:€|EUR)'
    labels = {'cold_eur': 'Kaltmiete|Nettokaltmiete', 'warm_eur': 'Warmmiete|Gesamtmiete',
              'costs_eur': 'Nebenkosten|Betriebskosten', 'deposit_eur': 'Kaution'}
    lines = text.splitlines()
    any_label = r'\b(?:' + '|'.join(labels.values()) + r')\b'
    for field, label in labels.items():
        match = None
        for pattern in (amount + gap + r'(?:' + label + r')\b',
                        r'\b(?:' + label + r')' + gap + ':?' + gap + amount):
            match = next((found for line in lines for found in [re.search(pattern, line, re.I)] if found), None)
            if match:
                break
        if match is None:
            for line, following in zip(lines, lines[1:]):
                if (re.fullmatch(gap + r'(?:' + label + r')' + gap + ':' + gap, line, re.I)
                        and not re.search(any_label, following, re.I)):
                    match = re.match(gap + amount, following, re.I)
                    if match:
                        break
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


def anchor_link(node, base_url):
    href = node.attrs.get('href', '').strip()
    return urljoin(base_url, href) if href and not href.startswith('#') else ''


def visible_text(node, excluded):
    if id(node) in excluded or node.tag in ('script', 'style', 'svg', 'head', 'title'):
        return ''
    if node.tag == 'br':
        return '\n'
    parts = [child if isinstance(child, str) else visible_text(child, excluded) for child in node.children]
    text = ' '.join(part for part in parts if part)
    text = re.sub(r'[ \t\r]*\n[ \t\r]*', '\n', text)
    text = re.sub(r'\n+', '\n', text).strip()
    if node.tag in ('dt', 'dd', 'tr', 'td', 'th', 'li', 'div', 'p', 'section', 'article',
                    'main', 'dl', 'table', 'ul', 'ol', 'h1', 'h2', 'h3'):
        if re.fullmatch(r'Kaltmiete|Nettokaltmiete|Warmmiete|Gesamtmiete|Nebenkosten|Betriebskosten|Kaution', text, re.I):
            text += ':'
        return '\n' + text + '\n'
    return text


def parse_html(text, base_url='', require_facts=True):
    if re.search(r'<title>[^<]*(?:captcha|access denied|just a moment|robot|zugriff verweigert)', text, re.I):
        return []
    if re.search(r'verify you are human|ich bin kein roboter|unusual traffic|cf-chl-|captcha-delivery\.com|captcha\s+(?:required|erforderlich)', text, re.I):
        return []
    root, rows = Document(text).root, []
    canonical, og_url = [], []
    for node in root.walk():
        if node.tag == 'link' and 'canonical' in node.attrs.get('rel', '').casefold().split():
            canonical.append(node.attrs.get('href', ''))
        elif node.tag == 'meta' and node.attrs.get('property', '').casefold() == 'og:url':
            og_url.append(node.attrs.get('content', ''))
    base_url = next((urljoin(base_url, candidate) for candidate in canonical + og_url
                     if identity(urljoin(base_url, candidate))), base_url)
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
        address = address if isinstance(address, dict) else {}
        size = item.get('floorSize')
        if isinstance(size, dict) and size.get('unitCode', size.get('unitText', 'MTK')) not in ('MTK', 'm2', 'm²'):
            size = None
        offer = item.get('offers')
        offer = offer if isinstance(offer, dict) and offer.get('priceCurrency', 'EUR') == 'EUR' else {}
        facts = normalize(Listing(row.source, row.source_id, row.url, row.title,
                                  street=address.get('streetAddress'), postcode=address.get('postalCode'),
                                  area_m2=quantity(size), rooms=quantity(item.get('numberOfRooms')),
                                  asking_eur=offer.get('price'), posted_at=item.get('datePosted') or item.get('datePublished')))
        for field in ('street', 'postcode', 'area_m2', 'rooms', 'asking_eur', 'posted_at'):
            value = getattr(facts, field)
            if value not in ('', None):
                setattr(row, field, value)
        rows.append(row)
    structured_count, main_identity, excluded = len(rows), identity(base_url), set()
    parents = {id(child): node for node in root.walk() for child in node.children if not isinstance(child, str)}
    for node in root.walk():
        if main_identity:
            break
        card = node.tag in ('article', 'li', 'tr') or (node.tag == 'div' and re.search(
            r'card|listing|expose|offer', node.attrs.get('class', ''), re.I))
        if not card:
            continue
        links = {}
        for child in node.walk():
            if child.tag == 'a':
                link = anchor_link(child, base_url)
                found = identity(link)
                if found:
                    links[found[:2]] = (link, child.text())
        if len(links) == 1:
            link, title = next(iter(links.values()))
            heading = next((child.text() for child in node.walk() if child.tag in ('h1', 'h2', 'h3')), '')
            rows.append(from_text(visible_text(node, set()), link, heading or title))
    for node in root.walk():
        if node.tag == 'a':
            if (set(node.attrs.get('rel', '').casefold().split()).intersection(('next', 'prev')) or
                    re.fullmatch(r'(?:next|previous)(?: listing)?', node.text().strip(), re.I)):
                continue
            link = anchor_link(node, base_url)
            found = identity(link)
            context = node
            if main_identity and found:
                if found[:2] == main_identity[:2]:
                    continue
                parent = parents.get(id(node))
                blocks = ('div', 'section', 'article', 'li', 'tr', 'td', 'p', 'aside', 'figure', 'main', 'body', 'html')
                while parent is not None and parent.tag not in blocks:
                    parent = parents.get(id(parent))
                if parent is not None:
                    ancestor = parents.get(id(parent))
                    while ancestor is not None and ancestor.tag not in ('main', 'body', 'html') and not any(
                            child.tag == 'h1' for child in ancestor.walk()):
                        if ancestor.tag in blocks:
                            parent = ancestor
                        ancestor = parents.get(id(ancestor))
                if parent is not None and parent.tag not in ('main', 'body', 'html') and not any(
                        child.tag == 'h1' for child in parent.walk()):
                    excluded.add(id(parent))
                    targets = {target[:2] for child in parent.walk() if child.tag == 'a'
                               for target in [identity(anchor_link(child, base_url))] if target}
                    if targets == {found[:2]}:
                        context = parent
                else:
                    excluded.add(id(node))
            heading = next((child.text() for child in context.walk() if child.tag in ('h2', 'h3')), node.text())
            row = from_text(visible_text(context, set()), link, heading)
            if row:
                rows.append(row)
    if main_identity:
        main = next((node for node in root.walk() if node.tag == 'main'), root)
        heading = next((node.text() for node in main.walk() if node.tag == 'h1'), '')
        heading = heading or next((node.text() for node in root.walk() if node.tag == 'title'), 'Imported offer')
        context = visible_text(main, excluded)
        if context and not re.search(r'captcha|access denied|verify you are human|kein roboter', heading, re.I):
            rows.insert(structured_count, from_text(context, base_url, heading))
    rows = merge(rows)
    return [row for row in rows if not require_facts or any(getattr(row, field) not in ('', None) for field in
            ('cold_eur', 'warm_eur', 'asking_eur', 'costs_eur', 'deposit_eur', 'area_m2', 'rooms', 'street', 'postcode'))]


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
                                        'reason': NO_LISTING if not rows and origin == 'saved_page' else
                                        'Offline import; not portal inventory or sender verification.'}},
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
        print(json.dumps({'listing_count': len(rows), 'status': 'imported' if rows else 'no_listing_found',
                          'hint': None if rows else NO_LISTING,
                          'output': 'flat-search/imported-page/results.json'}))
        return 0 if rows else 1
    except (OSError, ValueError, TypeError, RecursionError):
        parser.error('Saved page could not be imported; no URLs or private input contents logged.')


if __name__ == '__main__':
    raise SystemExit(main())
