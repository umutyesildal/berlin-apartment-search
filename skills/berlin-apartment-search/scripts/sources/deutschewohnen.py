"""Bounded public search-token flow; no account authentication or detail crawl."""

import json
from urllib.parse import urlencode
from guard import SourceError


NAME = 'deutschewohnen'
TOKEN_URL = 'https://www.deutsche-wohnen.com/api/real-estate/search-token'
SEARCH_URL = 'https://www.deutsche-wohnen.com/mieten/mietangebote?rentType=miete&city=Berlin&immoType=wohnung'
LIST_URL = 'https://www.deutsche-wohnen.com/api/deuwo-real-estate/list?' + urlencode(
    {'rentType': 'miete', 'city': 'Berlin', 'immoType': 'wohnung', 'dataSet': 'deuwo', 'limit': 50,
     'parkingCarport': 0, 'parkingStellplatz': 0, 'parkingGarage': 0, 'parkingTiefgarage': 0})


def probe(guard):
    data = json.loads(guard.fetch(NAME, TOKEN_URL, headers={'Accept': 'application/json', 'Referer': SEARCH_URL}))
    token = data.get('token') if isinstance(data, dict) else None
    if not isinstance(token, str) or not token.strip():
        raise SourceError('public search-token response missing token')
    return json.loads(guard.fetch(NAME, LIST_URL, headers={'Accept': 'application/json', 'Referer': SEARCH_URL,
                                                        'X-VON-Search-Token': token}))
