"""Weighted signals, not a fraud verdict. No signals does not mean safe."""

import json
import sys
from classify import positive_matches


RULES = {
    'advance_payment': (4, r'\b(?:vorkasse|vorauszahlung|advance payment|pay before viewing)\b'),
    'posted_keys': (4, r'\b(?:schlüssel.{0,25}(?:post|versand)|keys.{0,25}(?:post|mail|courier))\b'),
    'abroad': (2, r'\b(?:vermieter.{0,25}ausland|landlord.{0,25}abroad|ich (?:bin|lebe).{0,15}ausland)\b'),
    'irreversible_payment': (5, r'\b(?:western union|bitcoin|crypto(?:currency)?|kryptowährung)\b'),
    'whatsapp_only': (2, r'\b(?:(?:nur|only).{0,12}whatsapp|whatsapp.{0,12}(?:only|ausschließlich))\b'),
}


def assess(text, asking_per_m2=None, market_per_m2=None):
    signals = []
    for name, (weight, pattern) in RULES.items():
        evidence = list(positive_matches(text, pattern))
        if evidence:
            signals.append({'signal': name, 'weight': weight, 'evidence': evidence})
    if (asking_per_m2 is not None and market_per_m2 is not None
            and market_per_m2 > 0 and 0 < asking_per_m2 < 0.6 * market_per_m2):
        signals.append({'signal': 'far_below_supplied_market', 'weight': 2,
                        'evidence': ['below 60% of supplied market benchmark']})
    score = sum(item['weight'] for item in signals)
    return {'score': score, 'signals': signals,
            'review': 'high' if score >= 7 else 'elevated' if score else 'no_signals',
            'warning': 'Heuristic only; no signals does not establish safety.'}


if __name__ == '__main__':
    print(json.dumps(assess(sys.stdin.read()), ensure_ascii=False))
