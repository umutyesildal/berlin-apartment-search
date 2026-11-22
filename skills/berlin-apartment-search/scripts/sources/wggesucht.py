"""Public Berlin WG-room search cards, no detail fetches or account actions."""

import re
from urllib.parse import urljoin, urlsplit
from guard import Blocked, SourceError
from models import Listing, normalize, number
from sources.html_tools import Document


NAME = 'wggesucht'
URL = 'https://www.wg-gesucht.de/wg-zimmer-in-Berlin.8.0.1.0.html'


def parse(text):
    root = Document(text).root
    cards = [node for node in root.walk() if set(node.attrs.get('class', '').split()) & {'offer_list_item', 'wgg_card'}]
    output, seen = [], set()
    for card in cards:
        nodes = list(card.walk())
        link = next((node for node in nodes if re.search(r'\.\d+\.html(?:\?|$)', node.attrs.get('href', ''))), None)
        if link is None:
            raise SourceError('WG card missing listing URL')
        url = urljoin(URL, link.attrs['href']).split('?')[0]
        if urlsplit(url).hostname != 'www.wg-gesucht.de':
            raise SourceError('unexpected WG card host')
        identifier = re.search(r'\.(\d+)\.html$', url).group(1)
        if identifier in seen:
            continue
        seen.add(identifier)
        title = next((node.text() for node in nodes if node.tag in ('h2', 'h3')), '') or link.attrs.get('title', '')
        if not title:
            raise SourceError('WG card missing title')
        def field(token):
            return next((node.text() for node in nodes if token in node.attrs.get('class', '').split()), '')
        price = field('price-row') or field('col-xs-3')
        amount = re.search(r'(\d[\d., ]*)\s*€', price)
        area = field('card-offer-property-size')
        if not area:
            area = next((node.text() for node in nodes if re.fullmatch(r'\s*\d+(?:[,.]\d+)?\s*m[²2]\s*', node.text())), '')
        location = field('card-offer-details-text') or field('col-xs-11')
        rent = number(amount.group(1)) if amount else None
        output.append(normalize(Listing(NAME, identifier, url, title, district=location,
                                        area_m2=number(area), warm_eur=rent if 'gesamtmiete' in price.casefold() else None,
                                        asking_eur=rent, available_from=field('card-offer-availability'),
                                        text='WG-Zimmer ' + ' '.join((title, price, area, location)))))
    if not output and not re.search(r'keine angebote gefunden|keine passenden angebote|no results found|0 Angebote', text, re.I):
        raise Blocked('WG search shape missing or empty without explicit zero marker')
    return output


def search(guard, max_warm=None, min_rooms=None):
    return parse(guard.fetch(NAME, URL))
