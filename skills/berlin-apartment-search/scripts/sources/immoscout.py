"""Single-page anonymous mobile search. No detail fetch, login or messaging."""

import json
import re
from urllib.parse import urlencode
from guard import Blocked, SourceError
from models import Listing, normalize


NAME = 'immoscout'
URL = 'https://api.mobile.immobilienscout24.de/search/list'


def parse(text):
    try:
        data = json.loads(text)
    except ValueError as error:
        raise Blocked('non-JSON response') from error
    if not isinstance(data, dict) or not isinstance(data.get('resultListItems'), list):
        raise Blocked('missing result list envelope')
    output = []
    for result in data['resultListItems']:
        if not isinstance(result, dict):
            raise SourceError('invalid result card')
        if result.get('type') != 'EXPOSE_RESULT':
            continue
        item = result.get('item')
        if not isinstance(item, dict) or not item.get('id') or not item.get('title'):
            raise SourceError('invalid expose card')
        address = item.get('address') or {}
        attributes = item.get('attributes') or []
        if not isinstance(address, dict) or not isinstance(attributes, list):
            raise SourceError('invalid expose fields')
        listing = Listing(NAME, str(item['id']),
                          'https://www.immobilienscout24.de/expose/' + str(item['id']), item['title'],
                          posted_at=item.get('published', ''), latitude=address.get('lat'),
                          longitude=address.get('lon'), text=str(item['title']))
        line = str(address.get('line') or '')
        match = re.search(r'\b(\d{5})\b', line)
        listing.postcode = address.get('postcode') or (match.group(1) if match else '')
        if match and match.start() > 0:
            listing.street = line[:match.start()].strip(' ,')
        if ',' in line:
            listing.district = line.rsplit(',', 1)[-1].strip()
        for attribute in attributes:
            if not isinstance(attribute, dict):
                raise SourceError('invalid attribute')
            label, value = str(attribute.get('label', '')).casefold(), str(attribute.get('value', ''))
            if 'm²' in value or 'm2' in value:
                listing.area_m2 = value
            elif re.search(r'\b(?:zi\.?|zimmer)\b', value, re.I):
                listing.rooms = value
            elif '€' in value:
                if 'warm' in label or 'gesamt' in label:
                    listing.warm_eur = value
                elif 'kalt' in label:
                    listing.cold_eur = value
                else:
                    listing.asking_eur = value
        output.append(normalize(listing))
    if not output and data.get('totalResults') != 0:
        raise Blocked('no expose cards and no explicit zero total')
    return output


def search(guard, max_warm=None, min_rooms=None):
    params = {'searchType': 'region', 'geocodes': '/de/berlin/berlin',
              'realestatetype': 'apartmentrent', 'sorting': '-firstactivation', 'pagenumber': 1}
    if max_warm is not None:
        params.update(price='-' + str(max_warm), pricetype='calculatedtotalrent')
    if min_rooms is not None:
        params['numberofrooms'] = str(min_rooms) + '-'
    return parse(guard.fetch(NAME, URL + '?' + urlencode(params),
                            {'User-Agent': 'ImmoScout_28.9_27.2_._',
                             'Accept': 'application/json', 'Content-Type': 'application/json'},
                            b'{"supportedResultListTypes":[],"userData":{}}'))
