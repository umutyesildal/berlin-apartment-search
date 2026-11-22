"""Group plausible duplicates without dropping member identities or evidence."""

import json
import re
import sys
import unicodedata
from models import Listing, digest, normalize


def canonical(text):
    return re.sub(r'\W+', '', unicodedata.normalize('NFKC', text).casefold())


def fingerprint(item):
    return digest([canonical(item.postcode), canonical(item.street), item.rooms,
                   item.area_m2, item.cold_eur, item.warm_eur])


def possible_match(left, right):
    if left.id == right.id:
        return True
    if left.source == right.source:
        return False
    if not (left.postcode and left.street and right.postcode and right.street):
        return False
    if (canonical(left.postcode), canonical(left.street)) != (canonical(right.postcode), canonical(right.street)):
        return False
    if left.rooms is None or right.rooms is None or left.rooms != right.rooms:
        return False
    if left.area_m2 is None or right.area_m2 is None or abs(left.area_m2 - right.area_m2) > 2:
        return False
    for key in ('cold_eur', 'warm_eur'):
        a, b = getattr(left, key), getattr(right, key)
        if a is not None and b is not None:
            return abs(a - b) <= max(20, min(a, b) * 0.03)
    return False


def group(listings):
    groups = []
    for item in listings:
        for cluster in groups:
            if all(possible_match(item, existing) for existing in cluster):
                cluster.append(item)
                break
        else:
            groups.append([item])
    return [{'fingerprint': fingerprint(cluster[0]),
             'possible_duplicate': len(cluster) > 1,
             'members': [item.to_dict() for item in cluster]} for cluster in groups]


if __name__ == '__main__':
    print(json.dumps(group([normalize(Listing(**row)) for row in json.load(sys.stdin)]), ensure_ascii=False))
