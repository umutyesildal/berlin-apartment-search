"""SSR furnished-rental cards and Apartment JSON-LD; preserve price ambiguity."""

import json
import re
from urllib.parse import urljoin, urlsplit
from guard import Blocked, SourceError
from models import Listing, normalize, number
from sources.html_tools import Document


NAME = 'wunderflats'
URL = 'https://wunderflats.com/en/furnished-apartments/berlin'


def apartments(value):
    if isinstance(value, list):
        for item in value:
            yield from apartments(item)
    elif isinstance(value, dict):
        if value.get('@type') == 'Apartment':
            yield value
        for item in value.values():
            if isinstance(item, (dict, list)):
                yield from apartments(item)


def parse(text):
    root = Document(text).root
    metadata = {}
    for node in root.walk():
        if node.tag == 'script' and node.attrs.get('type') == 'application/ld+json':
            try:
                data = json.loads(node.text(scripts=True))
            except ValueError as error:
                raise SourceError('invalid Wunderflats JSON-LD') from error
            for apartment in apartments(data):
                identifiers = set()
                for key in ('url', '@id'):
                    value = apartment.get(key)
                    if isinstance(value, str):
                        parsed = urlsplit(urljoin(URL, value))
                        match = re.fullmatch(r'/en/furnished-apartment/[^/]+/([^/]+)/?', parsed.path)
                        if parsed.hostname == 'wunderflats.com' and match:
                            identifiers.add(match.group(1))
                value = apartment.get('identifier')
                value = value.get('value') if isinstance(value, dict) else value
                if isinstance(value, str) and re.fullmatch(r'[A-Za-z0-9_-]+', value):
                    identifiers.add(value)
                for identifier in identifiers:
                    metadata.setdefault(identifier, []).append(apartment)
    cards = [node for node in root.walk() if node.tag == 'article' and 'Listing' in node.attrs.get('class', '').split()]
    output, seen = [], set()
    for card in cards:
        nodes = list(card.walk())
        link = next((node for node in nodes if '/en/furnished-apartment/' in node.attrs.get('href', '')), None)
        if link is None:
            raise SourceError('Wunderflats card missing URL')
        url = urljoin(URL, link.attrs['href']).split('?')[0]
        if urlsplit(url).hostname != 'wunderflats.com':
            raise SourceError('unexpected Wunderflats card host')
        identifier = url.rstrip('/').rsplit('/', 1)[-1]
        if identifier in seen:
            continue
        seen.add(identifier)
        title = next((node.text() for node in nodes if node.tag in ('h2', 'h3')), '') or link.attrs.get('title', '')
        if not title:
            raise SourceError('Wunderflats card missing title')
        candidates = metadata.get(identifier, [])
        data = candidates[0] if len(candidates) == 1 else {}
        def field(token):
            return next((node.text() for node in nodes if token in node.attrs.get('class', '').split()), '')
        price = field('ListingPrice-price')
        if re.search(r'\d{1,3}(?:,\d{3})+(?!\d)', price):
            price = price.replace(',', '')
        area = data.get('floorSize')
        if isinstance(area, dict):
            area = area.get('value')
        address = data.get('address') or {}
        if not isinstance(address, dict):
            address = {}
        output.append(normalize(Listing(NAME, identifier, url, title, area_m2=area or number(field('ListingDetailsBrief-info--area')),
                                        rooms=data.get('numberOfRooms'), asking_eur=number(price),
                                        postcode=str(address.get('postalCode') or ''),
                                        district=str(address.get('addressLocality') or ''),
                                        text='Furnished temporary rental. ' + title + ' ' + field('Listing-details'))))
    if not output and not re.search(r'no apartments found|no results found|keine wohnungen gefunden', text, re.I):
        raise Blocked('Wunderflats search shape missing or empty without explicit zero marker')
    return output


def search(guard, max_warm=None, min_rooms=None):
    return parse(guard.fetch(NAME, URL))
