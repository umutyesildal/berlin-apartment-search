"""Bounded public search-token flow; no account authentication or detail crawl."""

import json
from urllib.parse import urlencode, urljoin, urlsplit
from guard import Blocked, SourceError
from models import Listing, normalize


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


def values(row):
    output = {}
    for key, value in row.items():
        if isinstance(value, dict):
            nested = values(value)
            for name, items in nested.items():
                output.setdefault(name, []).extend(items)
        elif isinstance(value, (str, int, float)) and not isinstance(value, bool):
            output.setdefault(key.casefold().replace('_', ''), []).append(value)
    return output


def pick(data, *names):
    for name in names:
        candidates = data.get(name.casefold().replace('_', ''), [])
        unique = list(dict.fromkeys(candidates))
        if len(unique) == 1:
            return unique[0]
    return None


def parse(data):
    if not isinstance(data, dict) or not isinstance(data.get('results'), list):
        raise Blocked('missing Deutsche Wohnen results envelope')
    output = []
    for row in data['results']:
        if not isinstance(row, dict):
            raise SourceError('invalid Deutsche Wohnen result')
        direct = values({key: value for key, value in row.items() if not isinstance(value, (dict, list))})
        facts = values(row)
        identifier = pick(direct, 'objectId', 'objektId', 'id', 'propertyId')
        if identifier is None or not str(identifier).strip():
            raise SourceError('Deutsche Wohnen card missing stable identity; schema may have changed')
        link = pick(direct, 'detailUrl', 'exposeUrl', 'url')
        url = urljoin(SEARCH_URL, str(link)) if link else ''
        if url and (urlsplit(url).scheme != 'https' or urlsplit(url).hostname != 'www.deutsche-wohnen.com'):
            url = ''
        title = str(pick(direct, 'title', 'titel', 'heading') or 'Deutsche Wohnen offer ' + str(identifier))
        listing = Listing(NAME, str(identifier), url, title,
                          district=pick(facts, 'district', 'stadtteil'), postcode=pick(facts, 'postcode', 'postalCode', 'plz'),
                          street=pick(facts, 'street', 'streetName', 'strasse'),
                          rooms=pick(facts, 'rooms', 'numberOfRooms', 'zimmer'),
                          area_m2=pick(facts, 'livingArea', 'wohnflaeche', 'area'),
                          cold_eur=pick(facts, 'netColdRent', 'coldRent', 'kaltmiete'),
                          warm_eur=pick(facts, 'totalRent', 'warmRent', 'gesamtmiete', 'warmmiete'),
                          costs_eur=pick(facts, 'additionalCosts', 'nebenkosten'),
                          asking_eur=pick(facts, 'price', 'preis'),
                          deposit_eur=pick(facts, 'deposit', 'kaution'),
                          available_from=pick(facts, 'availableFrom', 'verfuegbarAb'),
                          posted_at=pick(facts, 'publishedAt', 'postedAt'),
                          latitude=pick(facts, 'latitude', 'lat'), longitude=pick(facts, 'longitude', 'lon'),
                          text=title + '\n' + str(pick(direct, 'description', 'beschreibung') or ''))
        output.append(normalize(listing))
    return output


def search(guard, max_warm=None, min_rooms=None):
    return parse(probe(guard))
