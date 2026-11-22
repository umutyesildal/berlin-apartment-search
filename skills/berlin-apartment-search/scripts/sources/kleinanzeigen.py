"""Search cards plus card JSON-LD, independent of site CSS redesigns."""

import json
import re
from urllib.parse import urljoin
from guard import Blocked, SourceError
from models import Listing, normalize
from sources.html_tools import Document


NAME = 'kleinanzeigen'
URL = 'https://www.kleinanzeigen.de/s-wohnung-mieten/berlin/c203l3331'


def parse(text):
    root = Document(text).root
    output = []
    for card in root.walk():
        if card.tag != 'article' or not card.attrs.get('data-adid'):
            continue
        nodes = list(card.walk())
        title = next((node.text() for node in nodes if node.tag in ('h2', 'h3')), '')
        url = card.attrs.get('data-href') or next((node.attrs['href'] for node in nodes
                                                  if '/s-anzeige/' in node.attrs.get('href', '')), '')
        description = ' '.join(node.text() for node in nodes if node.tag == 'p')
        for node in nodes:
            if node.tag == 'script' and node.attrs.get('type') == 'application/ld+json':
                try:
                    data = json.loads(node.text(scripts=True))
                except ValueError as error:
                    raise SourceError('invalid card JSON-LD') from error
                if isinstance(data, dict):
                    title = title or str(data.get('title') or data.get('name') or '')
                    description = description or str(data.get('description') or '')
        if not title or not url:
            raise SourceError('card missing title or URL')
        card_text = card.text()
        price = re.search(r'(\d[\d.,\s\u00a0]*)\s*€', card_text)
        area = re.search(r'(\d+(?:[,.]\d+)?)\s*m[²2]', card_text)
        rooms = re.search(r'(\d+(?:[,.]\d+)?)\s*(?:Zi\.?|Zimmer)\b', card_text, re.I)
        location = next((node.text() for node in nodes if node.tag in ('span', 'div')
                         and re.match(r'^\d{5}\s+[^\d]+$', node.text()) and len(node.text()) < 100), '')
        date = next((node.text() for node in nodes if node.tag == 'time'), '')
        item = Listing(NAME, card.attrs['data-adid'], urljoin(URL, url), title,
                       postcode=location[:5], district=location[5:].strip(),
                       rooms=rooms.group(1) if rooms else None, area_m2=area.group(1) if area else None,
                       asking_eur=price.group(1) if price else None, posted_at=date,
                       text=' '.join((title, description, card_text)))
        output.append(normalize(item))
    if not output and not re.search(r'keine (?:anzeigen|ergebnisse)|0 ergebnisse', root.text(), re.I):
        raise Blocked('no cards or explicit zero-result message')
    return output


def search(guard, max_warm=None, min_rooms=None):
    return parse(guard.fetch(NAME, URL))
