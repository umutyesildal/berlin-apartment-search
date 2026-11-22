"""Conditional arithmetic, never an automated legal determination."""

import json
import math
import sys


def assess(cold_eur=None, area_m2=None, costs_eur=None, deposit_eur=None,
           comparison_per_m2=None, comparison_source=None, data_as_of=None,
           exceptions=None):
    for value in (cold_eur, area_m2, costs_eur, deposit_eur, comparison_per_m2):
        if value is not None and (isinstance(value, bool) or not isinstance(value, (int, float))
                                  or not math.isfinite(value) or value < 0):
            raise ValueError('rent inputs must be finite non-negative numbers or null')
    if area_m2 == 0 or comparison_per_m2 == 0:
        raise ValueError('area and comparison must be positive when supplied')
    rate = cold_eur / area_m2 if cold_eur is not None and area_m2 else None
    costs_rate = costs_eur / area_m2 if costs_eur is not None and area_m2 else None
    comparison = {'status': 'unknown', 'reason': 'applicable dated comparison and coverage needed'}
    if comparison_per_m2 and comparison_source and data_as_of and rate is not None:
        limit = comparison_per_m2 * 1.1
        comparison = {'status': 'exception_review' if exceptions else 'conditional_comparison',
                      'above_plus_10_percent': rate > limit + 1e-9,
                      'conditional_limit_per_m2': round(limit, 2),
                      'source': comparison_source, 'data_as_of': data_as_of}
    return {
        'orientation': 'orientation, not legal advice',
        'cold_per_m2': round(rate, 2) if rate is not None else None,
        'comparison': comparison,
        'exceptions': exceptions or [],
        'exceptions_to_check': ['first used and let after 2014-10-01',
                                'first letting after comprehensive modernization',
                                'qualifying higher prior rent', 'recent modernization adjustment',
                                'coverage, tenancy date and special arrangements'],
        'deposit_above_three_cold': (deposit_eur > 3 * cold_eur if deposit_eur is not None
                                     and cold_eur is not None and cold_eur > 0 else None),
        'costs_per_m2': round(costs_rate, 2) if costs_rate is not None else None,
        'costs_review': (not 0.8 <= costs_rate <= 6 if costs_rate is not None else None),
        'costs_note': '0.80–6.00 €/m² is a broad heuristic, not a legal threshold',
    }


if __name__ == '__main__':
    try:
        print(json.dumps(assess(**json.load(sys.stdin)), ensure_ascii=False))
    except (ValueError, TypeError) as error:
        print(str(error), file=sys.stderr)
        sys.exit(2)
