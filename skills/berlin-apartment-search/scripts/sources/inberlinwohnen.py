"""Decode public server-rendered Livewire snapshots, not the update protocol."""

import json
from guard import Blocked, SourceError
from models import Listing, number, normalize
from sources.html_tools import Document


NAME = 'inberlinwohnen'
URL = 'https://www.inberlinwohnen.de/wohnungsfinder/?page=1'


def unwrap(value):
    if isinstance(value, list):
        if len(value) == 2 and isinstance(value[1], dict) and value[1].get('s') in ('arr', 'clctn'):
            return unwrap(value[0])
        return [unwrap(child) for child in value]
    if isinstance(value, dict):
        return {key: unwrap(child) for key, child in value.items()}
    return value


def detail_pairs(value):
    if isinstance(value, dict):
        if 'label' in value and 'value' in value:
            yield str(value['label']).casefold(), str(value['value'])
        for child in value.values():
            yield from detail_pairs(child)
    elif isinstance(value, list):
        for child in value:
            yield from detail_pairs(child)


def parse(text):
    output, explicit_empty = [], False
    for node in Document(text).root.walk():
        snapshot = node.attrs.get('wire:snapshot')
        if not snapshot:
            continue
        try:
            raw = json.loads(snapshot)
        except ValueError as error:
            raise SourceError('invalid Livewire JSON') from error
        data = unwrap(raw.get('data', {})) if isinstance(raw, dict) else {}
        if not isinstance(data, dict):
            continue
        if data.get('itemIds') == [] and number(data.get('itemsPerPage')):
            explicit_empty = True
        item = data.get('item')
        if not item:
            continue
        if not isinstance(item, dict) or not item.get('id') or not item.get('title'):
            raise SourceError('invalid listing snapshot')
        address = item.get('address') or {}
        if not isinstance(address, dict):
            raise SourceError('invalid snapshot address')
        details = dict(detail_pairs(item.get('details', [])))
        wbs_text = details.get('wbs', '').casefold()
        wbs = None if not wbs_text else not any(s in wbs_text for s in ('nein', 'nicht', 'kein', 'ohne'))
        listing = Listing(NAME, str(item['id']), item.get('deeplink', ''), item['title'],
                          district=address.get('district', ''), postcode=address.get('zipCode', ''),
                          street=' '.join(str(address.get(k) or '') for k in ('street', 'number')).strip(),
                          rooms=item.get('rooms'), area_m2=item.get('area'),
                          cold_eur=item.get('rentNet'), costs_eur=item.get('extraCosts'),
                          warm_eur=details.get('gesamtmiete') or item.get('rentGross'),
                          deposit_eur=details.get('kaution'), wbs=wbs,
                          available_from=item.get('occupationDate', ''), posted_at=item.get('createdAt', ''),
                          latitude=address.get('lat'), longitude=address.get('lon'),
                          text=' '.join([str(item['title'])] + [k + ': ' + v for k, v in details.items()]))
        if item.get('exchangeRequestId'):
            listing.text += ' Tauschwohnung'
        output.append(normalize(listing))
    if not output and not explicit_empty:
        raise Blocked('no recognized listing snapshots or explicit empty result')
    return output


def search(guard, max_warm=None, min_rooms=None):
    return parse(guard.fetch(NAME, URL))
