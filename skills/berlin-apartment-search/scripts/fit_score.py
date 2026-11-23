"""Transparent preference fit, independent of scam and legal assessments."""

import argparse
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path


WEIGHTS = {'budget': 25, 'size_rooms': 20, 'district': 15, 'value': 10,
           'costs': 10, 'freshness': 10, 'commute': 10}


def positive(value):
    if isinstance(value, bool):
        return None
    try:
        value = float(value)
        return value if math.isfinite(value) and value > 0 else None
    except (TypeError, ValueError):
        return None


def validate_profile(profile):
    profile = {} if profile is None else profile
    if not isinstance(profile, dict):
        raise ValueError('profile must be an object')
    for key in ('max_warm_eur', 'min_rooms', 'min_area_m2', 'value_eur_m2', 'max_commute_minutes'):
        if profile.get(key) is not None and positive(profile[key]) is None:
            raise ValueError('profile preference must be positive and finite: ' + key)
    districts = profile.get('districts')
    if districts is not None and (not isinstance(districts, list) or
                                  any(not isinstance(item, str) or not item.strip() for item in districts)):
        raise ValueError('districts must be a list of nonempty strings')
    return dict(profile)


def weights_from(overrides=None):
    weights = dict(WEIGHTS)
    if overrides is not None and not isinstance(overrides, dict):
        raise ValueError('weights must be a JSON object')
    for name, value in (overrides or {}).items():
        if name not in weights or isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError('invalid weight: ' + name)
        if not math.isfinite(value) or value < 0:
            raise ValueError('weights must be finite and non-negative')
        weights[name] = value
    if not sum(weights.values()):
        raise ValueError('at least one weight must be positive')
    return weights


def score(listing, profile=None, weights=None, now=None):
    profile = profile or {}
    weights = weights_from(weights)
    factors = {key: {'points': 50, 'status': 'unknown', 'reason': 'Missing listing data or preference; neutral 50.'}
               for key in WEIGHTS}

    def known(key, points, reason):
        factors[key] = {'points': round(max(0, min(100, points)), 2), 'status': 'known', 'reason': reason}

    warm, budget = positive(listing.get('warm_eur')), positive(profile.get('max_warm_eur'))
    if warm and budget:
        known('budget', 100 if warm <= budget else max(0, 100 - 200 * (warm / budget - 1)),
              'Warm rent %.2f EUR / budget %.2f EUR.' % (warm, budget))
    dimensions, reasons = [], []
    for field, target in (('area_m2', 'min_area_m2'), ('rooms', 'min_rooms')):
        actual, minimum = positive(listing.get(field)), positive(profile.get(target))
        dimensions.append(min(100, 100 * actual / minimum) if actual and minimum else 50)
        reasons.append('%s: %s / minimum %s' % (field, actual, minimum))
    if any(positive(listing.get(field)) and positive(profile.get(target))
           for field, target in (('area_m2', 'min_area_m2'), ('rooms', 'min_rooms'))):
        known('size_rooms', sum(dimensions) / len(dimensions), '; '.join(reasons) + '; missing dimension neutral.')
    districts, district = profile.get('districts'), str(listing.get('district') or '').strip().casefold()
    if districts and district:
        known('district', 100 if district in [str(item).strip().casefold() for item in districts] else 0,
              'Exact district preference match.' if district in [str(item).strip().casefold() for item in districts]
              else 'Outside supplied preferred districts; verify portal district label.')
    area, cold, benchmark = (positive(listing.get('area_m2')), positive(listing.get('cold_eur')),
                             positive(profile.get('value_eur_m2')))
    if area and cold and benchmark:
        known('value', 50 + 100 * (1 - cold / area / benchmark),
              'Cold %.2f EUR/m² vs user-supplied value benchmark %.2f; not a legal comparison.' % (cold / area, benchmark))
    costs = positive(listing.get('costs_eur'))
    if listing.get('costs_eur') == 0 and not isinstance(listing.get('costs_eur'), bool):
        costs = 0
    if area and costs is not None:
        known('costs', 100 if 0.8 <= costs / area <= 6 else 0,
              'Ancillary %.2f EUR/m²; broad heuristic band 0.80–6.00, not a bill forecast.' % (costs / area))
    try:
        posted = datetime.fromisoformat(str(listing.get('posted_at') or '').replace('Z', '+00:00'))
        posted = posted.replace(tzinfo=timezone.utc) if posted.tzinfo is None else posted
        age = ((now or datetime.now(timezone.utc)) - posted).total_seconds() / 86400
        if age >= 0:
            known('freshness', 100 * (1 - min(age, 30) / 30), 'Posted %.1f days ago; linear 30-day horizon.' % age)
    except (ValueError, TypeError):
        pass
    commute = listing.get('commute') or {}
    minutes, limit = positive(commute.get('minutes')), positive(profile.get('max_commute_minutes'))
    if commute.get('status') == 'ok' and minutes and limit:
        known('commute', 100 if minutes <= limit else max(0, 100 - 100 * (minutes / limit - 1)),
              'Route %.1f minutes / preference %.1f minutes; estimate only.' % (minutes, limit))
    for key in factors:
        factors[key]['weight'] = weights[key]
    return {'score': round(sum(factors[key]['points'] * weights[key] for key in weights) / sum(weights.values()), 1),
            'factors': factors, 'warning': 'Preference fit only. Review scam, integrity and rent flags separately.'}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile', type=Path)
    parser.add_argument('--weights', default='{}', help='JSON dict of factor weight overrides')
    args = parser.parse_args(argv)
    try:
        profile = validate_profile(json.loads(args.profile.read_text(encoding='utf-8')) if args.profile else {})
        print(json.dumps(score(json.load(sys.stdin), profile, json.loads(args.weights)), ensure_ascii=False))
        return 0
    except (OSError, ValueError, TypeError, AttributeError) as error:
        parser.error(str(error))


if __name__ == '__main__':
    main()
