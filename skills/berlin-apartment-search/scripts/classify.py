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


def positive_matches(text, pattern, noise=False):
    normalized = ' '.join(text.split())
    prefixes = r'kein(?:e|en)?(?:\s+Zahlung\s+(?:per|als))?|ohne|no|without'
    if noise:
        prefixes += r'|kein(?:e|en)?\s+Wohnung\s+per|nicht|not'
    for match in re.finditer(pattern, normalized, re.I):
        before, after = normalized[:match.start()], normalized[match.end():]
        negated_before = re.search(r'\b(?:' + prefixes + r')\s+$', before, re.I)
        negated_after = re.match(
            r'\s+(?:ist\s+)?(?:nicht\s+(?:erforderlich|nötig|notwendig|gewünscht|erwünscht|möglich)'
            r'|keine\s+Pflicht)\b', after, re.I)
        if not negated_before and not negated_after:
            yield match.group()


def classify(text):
    return [tag for tag, pattern in PATTERNS.items() if list(positive_matches(text, pattern, noise=True))]


if __name__ == '__main__':
    print(json.dumps(classify(sys.stdin.read()), ensure_ascii=False))
