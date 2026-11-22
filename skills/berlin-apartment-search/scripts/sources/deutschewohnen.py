"""Bounded public search-token flow; no account authentication or detail crawl."""

import json
import re
from urllib.parse import quote, urlencode
from guard import Blocked, SourceError
from models import Listing, coordinate, normalize


NAME = 'deutschewohnen'
TOKEN_URL = 'https://www.deutsche-wohnen.com/api/real-estate/search-token'
SEARCH_URL = 'https://www.deutsche-wohnen.com/mieten/mietangebote?rentType=miete&city=Berlin&immoType=wohnung'
LIST_URL = 'https://www.deutsche-wohnen.com/api/deuwo-real-estate/list?' + urlencode(
    {'rentType': 'miete', 'city': 'Berlin', 'immoType': 'wohnung', 'dataSet': 'deuwo', 'limit': 50,
     'parkingCarport': 0, 'parkingStellplatz': 0, 'parkingGarage': 0, 'parkingTiefgarage': 0})


def probe(guard):
    try:
        data = json.loads(guard.fetch(NAME, TOKEN_URL, headers={'Accept': 'application/json', 'Referer': SEARCH_URL}))
    except ValueError as error:
        raise Blocked('public search-token returned non-JSON') from error
    token = data.get('token') if isinstance(data, dict) else None
    if not isinstance(token, str) or not token.strip():
        raise SourceError('public search-token response missing token')
    try:
        return json.loads(guard.fetch(NAME, LIST_URL, headers={'Accept': 'application/json', 'Referer': SEARCH_URL,
                                                            'X-VON-Search-Token': token}))
    except ValueError as error:
        raise Blocked('public list returned non-JSON') from error


def parse(data):
    if not isinstance(data, dict) or not isinstance(data.get('results'), list):
        raise Blocked('missing Deutsche Wohnen results envelope')
    output = []
    for row in data['results']:
        if not isinstance(row, dict):
            raise SourceError('invalid Deutsche Wohnen result')
        identifier = row.get('wrk_id')
        if isinstance(identifier, bool) or not isinstance(identifier, (str, int)) or not str(identifier).strip():
            raise SourceError('Deutsche Wohnen card missing stable identity; schema may have changed')
        slug = row.get('slug')
        url = ('https://www.deutsche-wohnen.com/mieten/mietangebote/' + quote(slug, safe='-')
               if isinstance(slug, str) and re.fullmatch(r'[\w-]{1,500}', slug) else '')
        title = str(row.get('titel') or 'Deutsche Wohnen offer ' + str(identifier))
        latitude, longitude = coordinate(row.get('lat')), coordinate(row.get('lng'))
        if not latitude or not longitude or not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
            latitude = longitude = None
        listing = Listing(NAME, str(identifier), url, title,
                          postcode=row.get('plz', ''), street=row.get('strasse', ''),
                          rooms=row.get('anzahl_zimmer'), area_m2=row.get('groesse'), asking_eur=row.get('preis'),
                          latitude=latitude, longitude=longitude,
                          text=title + '\n' + str(row.get('strasse') or '') + '\n' + str(row.get('ort') or ''))
        output.append(normalize(listing))
    return output


def search(guard, max_warm=None, min_rooms=None):
    return parse(probe(guard))
