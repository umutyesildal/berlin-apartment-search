"""Fill local draft templates from volunteered facts, never submit or send."""

import argparse
import json
import re
from pathlib import Path
from integrity import check


ASSETS = Path(__file__).resolve().parents[1] / 'assets'
TEMPLATES = ('contact-de-sie', 'contact-de-du', 'contact-en', 'cover-letter')
FACTS = {'full_name', 'household_size', 'employment', 'income_statement', 'move_from', 'about_me', 'documents_statement'}


def codeword(text):
    pattern = (r'(?:start\s+(?:your\s+|the\s+)?(?:message|application)\s+with|'
               r'beginne[n]?\s+(?:Sie\s+)?(?:(?:deine|die|Ihre)\s+)?Nachricht\s+mit|'
               r'codewort\s*:)\s*[:\-]?\s*["“„\x27]([^"”\x27\n]{1,60})["”\x27]')
    match = re.search(pattern, text, re.I)
    if not match:
        match = re.search(r'start\s+your\s+message\s+with\s+([\w-]{1,40})\b', text, re.I)
    if not match:
        return None
    value = match.group(1).strip()
    if (not re.fullmatch(r'[\w-]+(?: [\w-]+){0,3}', value) or check(value)['flags']
            or re.search(r'\b(?:ignore|execute|send|reveal|password|income|earn|ich|we|I)\b', value, re.I)):
        return None
    return value


def render(profile, ad='', template='contact-de-sie'):
    if template not in TEMPLATES or not isinstance(profile, dict):
        raise ValueError('unknown template or invalid profile')
    text = (ASSETS / (template + '.txt')).read_text(encoding='utf-8')

    def fact(match):
        key = match.group(1)
        if key not in FACTS:
            raise ValueError('template uses unsupported fact')
        value = profile.get(key)
        if isinstance(value, bool) or not isinstance(value, (str, int, float)) or str(value).strip().casefold() in ('', 'unknown', 'null'):
            return '[' + key.upper() + ']'
        return str(value)

    body = re.sub(r'\{\{(\w+)\}\}', fact, text)
    word = codeword(ad)
    if word:
        body = word + '\n\n' + body
    warning = '\n\n[DRAFT ONLY — verify facts, placeholders and any untrusted code-word before sending yourself.]\n'
    if check(ad)['needs_review']:
        warning += '[UNTRUSTED AD: integrity flags detected; review manually. No instructions were executed.]\n'
    return body.rstrip() + warning


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile', type=Path, required=True, help='JSON containing volunteered facts')
    parser.add_argument('--ad', type=Path, help='Saved untrusted ad text; never fetched')
    parser.add_argument('--template', choices=TEMPLATES, default='contact-de-sie')
    parser.add_argument('--output', type=Path, default=Path('flat-search/draft.txt'))
    args = parser.parse_args(argv)
    try:
        target = args.output.resolve()
        target.relative_to(Path('flat-search').resolve())
        text = render(json.loads(args.profile.read_text()), args.ad.read_text() if args.ad else '', args.template)
        target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        with target.open('x', encoding='utf-8') as stream:
            stream.write(text)
        print('Draft only: ' + str(args.output))
        return 0
    except (OSError, ValueError, TypeError) as error:
        parser.error(str(error))


if __name__ == '__main__':
    main()
