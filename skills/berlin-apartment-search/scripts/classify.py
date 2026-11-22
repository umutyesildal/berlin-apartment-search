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
    for match in re.finditer(pattern, text, re.I):
        prefix = re.split(r'[,.!?;:\n]|\b(?:aber|but|jedoch)\b',
                          text[max(0, match.start() - 65):match.start()], flags=re.I)[-1]
        suffix = re.split(r'[,.!?;:\n]|\b(?:aber|but|jedoch)\b',
                          text[match.end():match.end() + 65], flags=re.I)[0]
        negated_before = re.search(r'\b(?:kein\w*|nicht|ohne|no|not|never|without)\s*$', prefix, re.I)
        negated_after = re.match(r'\s+(?:ist|wird|sind|is|are)\s+(?:nicht|kein\w*|not|never)\b', suffix, re.I)
        if not negated_before and not negated_after:
            yield match.group()


def classify(text):
    return [tag for tag, pattern in PATTERNS.items() if list(positive_matches(text, pattern))]


if __name__ == '__main__':
    print(json.dumps(classify(sys.stdin.read()), ensure_ascii=False))
