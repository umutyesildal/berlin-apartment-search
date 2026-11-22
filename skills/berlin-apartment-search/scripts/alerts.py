"""Parse user-exported alert .eml files offline; never accesses an inbox or URLs."""

import argparse
import json
from email import policy
from email.parser import BytesParser
from pathlib import Path
from import_page import MAX_BYTES, build_report, merge, parse_html, parse_text
from search import write_report


def text_parts(message):
    if message.get_content_disposition() == 'attachment':
        return
    if message.get_content_maintype() == 'multipart':
        for part in message.iter_parts():
            yield from text_parts(part)
    elif message.get_content_type() in ('text/plain', 'text/html'):
        yield message


def parse(data):
    if not isinstance(data, bytes) or len(data) > MAX_BYTES:
        raise ValueError('alert must be bytes, at most 5 MiB')
    message = BytesParser(policy=policy.default).parsebytes(data)
    rows = []
    for part in text_parts(message):
        payload = part.get_payload(decode=True) or b''
        charset = part.get_content_charset() or 'utf-8'
        try:
            text = payload.decode(charset, errors='replace')
        except LookupError:
            text = payload.decode('utf-8', errors='replace')
        rows.extend(parse_html(text, require_facts=False) if part.get_content_type() == 'text/html' else parse_text(text))
    return merge(rows)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('emails', type=Path, nargs='+')
    args = parser.parse_args(argv)
    try:
        rows = []
        for path in args.emails:
            if path.stat().st_size > MAX_BYTES:
                raise ValueError('alert exceeds 5 MiB')
            rows.extend(parse(path.read_bytes()))
        rows = merge(rows)
        write_report(build_report(rows, 'saved_alerts'), Path('flat-search/alerts'))
        print(json.dumps({'listing_count': len(rows), 'status': 'imported' if rows else 'unrecognized',
                          'output': 'flat-search/alerts/results.json'}))
        return 0 if rows else 1
    except (OSError, ValueError, TypeError, RecursionError):
        parser.error('Alert import failed; no private message headers or contents logged.')


if __name__ == '__main__':
    raise SystemExit(main())
