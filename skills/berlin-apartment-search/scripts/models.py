"""Common, deliberately nullable listing schema and small parsing primitives."""

import hashlib
import json
import math
import re
from dataclasses import asdict, dataclass, field
from typing import Optional
from urllib.parse import urlsplit


def number(value):
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (float, int)):
        return float(value) if math.isfinite(value) else None
    text = str(value).replace('\u00a0', '').replace(' ', '')
    match = re.search(r'-?\d[\d.,]*', text)
    if not match:
        return None
    text = match.group().rstrip('.,')
    if ',' in text:
        text = text.replace('.', '').replace(',', '.')
    elif re.fullmatch(r'\d{1,3}(?:\.\d{3})+', text):
        text = text.replace('.', '')
    try:
        result = float(text)
        return result if math.isfinite(result) else None
    except ValueError:
        return None


def safe_url(value):
    value = str(value or '')
    parsed = urlsplit(value)
    if parsed.scheme == 'https' and parsed.hostname and not parsed.username and not parsed.password:
        return value
    return ''


@dataclass
class Listing:
    source: str
    source_id: str
    url: str
    title: str
    district: str = ''
    postcode: str = ''
    street: str = ''
    rooms: Optional[float] = None
    area_m2: Optional[float] = None
    cold_eur: Optional[float] = None
    warm_eur: Optional[float] = None
    asking_eur: Optional[float] = None
    costs_eur: Optional[float] = None
    deposit_eur: Optional[float] = None
    wbs: Optional[bool] = None
    available_from: str = ''
    posted_at: str = ''
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    text: str = ''
    tags: list = field(default_factory=list)

    @property
    def id(self):
        return self.source + ':' + self.source_id

    def to_dict(self):
        return dict(asdict(self), id=self.id)


def normalize(item):
    if not item.source or not str(item.source_id).strip():
        raise ValueError('missing source identity')
    item.source_id = str(item.source_id)
    item.url = safe_url(item.url)
    for key in ('rooms', 'area_m2', 'cold_eur', 'warm_eur', 'asking_eur',
                'costs_eur', 'deposit_eur', 'latitude', 'longitude'):
        value = number(getattr(item, key))
        if key not in ('latitude', 'longitude') and value is not None and value < 0:
            value = None
        if key in ('rooms', 'area_m2') and value == 0:
            value = None
        setattr(item, key, value)
    for key in ('title', 'district', 'postcode', 'street', 'available_from', 'posted_at', 'text'):
        setattr(item, key, str(getattr(item, key) or '').strip())
    return item


def digest(parts):
    return hashlib.sha256(json.dumps(parts, ensure_ascii=False, sort_keys=True).encode()).hexdigest()[:20]
