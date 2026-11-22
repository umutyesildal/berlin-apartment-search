"""Conservative, multi-label noise tags; caller decides whether to exclude."""

import json
import re
import sys


PATTERNS = {
    'swap': r'\b(?:tauschwohnung|wohnungstausch|tauschangebot|tausch|swap)\b',
    'wg': r'\b(?:wg(?:[- ]zimmer)?|wohngemeinschaft|flatshare|shared room)\b',
    'sublet': r'\b(?:zwischenmiete|untermiete|untermieter|sublet)\b',
    'wanted': r'\b(?:wohnungsgesuch|mietgesuch|suche(?:n)? (?:eine? )?wohnung|wohnung gesucht|looking for (?:a )?flat)\b',
    'furnished': r'\b(?:möbliert\w*|moebliert\w*|furnished)\b',
    'temporary': r'\b(?:befristet\w*|auf zeit|temporary|kurzzeit\w*|zwischenmiete)\b',
}


def positive_matches(text, pattern):
    clauses = re.split(r'[,.!?;:\n]|\b(?:aber|but|jedoch)\b', text, flags=re.I)
    for clause in clauses:
        for match in re.finditer(pattern, clause, re.I):
            before = re.findall(r'\w+', clause[:match.start()].casefold())[-3:]
            after = re.findall(r'\w+', clause[match.end():].casefold())[:2]
            negated_before = any(re.fullmatch(r'kein\w*|nicht|ohne|no|not|never|without', token)
                                 for token in before)
            negated_after = any(re.fullmatch(r'kein\w*|nicht|not|never', token) for token in after)
            if not negated_before and not negated_after:
                yield match.group()


def classify(text):
    return [tag for tag, pattern in PATTERNS.items() if list(positive_matches(text, pattern))]


if __name__ == '__main__':
    print(json.dumps(classify(sys.stdin.read()), ensure_ascii=False))
