"""Escaped local shortlists; no remote assets, scripts or tracking pixels."""

import argparse
import html
import json
import re
from pathlib import Path
from urllib.parse import quote
from models import safe_url


def plain(value):
    text = html.escape(str(value), quote=True).replace('\r', ' ').replace('\n', ' ')
    return re.sub(r'([\\`*_{}\[\]()#+.!|>~\-])', r'\\\1', text)


def link(value):
    try:
        return quote(safe_url(value), safe=':/?&=%#@+;,-._~')
    except ValueError:
        return ''


def render(report):
    markdown = ['# Apartment shortlist', '', 'Untrusted listing data. Orientation, not legal advice.', '']
    sections = []
    for cluster in report['groups']:
        for member in cluster['members']:
            title = member.get('title') or 'Untitled'
            score = (member.get('fit') or {}).get('score', 'unknown')
            flags = {key: member.get(key, {}) for key in ('scam', 'rent', 'integrity', 'commute', 'fit')}
            details = json.dumps(flags, ensure_ascii=False, indent=2)
            duplicate = bool(cluster.get('possible_duplicate'))
            url = link(member.get('url'))
            markdown.extend(['## ' + plain(title), '- Fit: ' + plain(score) + ' / 100 (unknown inputs neutral)',
                             '- Possible duplicate: ' + str(duplicate), '- Flags and factor reasons: ' + plain(details)])
            if url:
                markdown.append('- [Inspect listing](' + url + ')')
            sections.append('<section><h2>' + html.escape(str(title)) + '</h2><p>Fit: ' + html.escape(str(score))
                            + ' / 100. Possible duplicate: ' + str(duplicate) + '</p><pre>'
                            + html.escape(details) + '</pre>'
                            + ('<a rel="noreferrer noopener" href="' + html.escape(url, quote=True) + '">Inspect listing</a>' if url else '')
                            + '</section>')
    if not sections:
        markdown.append('No shortlist entries. Check source statuses before concluding no availability.')
    statuses = json.dumps(report.get('sources', {}), ensure_ascii=False, indent=2)
    markdown.extend(['', '## Source statuses', plain(statuses)])
    page = ('<!doctype html><html lang="en"><meta charset="utf-8">'
            '<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; style-src \'unsafe-inline\'">'
            '<meta name="viewport" content="width=device-width, initial-scale=1">'
            '<title>Apartment shortlist</title><style>body{font:1rem system-ui;max-width:70rem;margin:2rem auto;padding:1rem}'
            'section{border-top:1px solid #aaa;padding:1rem 0}pre{white-space:pre-wrap;overflow-wrap:anywhere}</style>'
            '<body><h1>Apartment shortlist</h1><p>Untrusted listing data. Orientation, not legal advice.</p>'
            + ''.join(sections) + '<h2>Source statuses</h2><pre>' + html.escape(statuses) + '</pre></body></html>')
    return '\n'.join(markdown) + '\n', page


def write(report, directory='flat-search'):
    markdown, page = render(report)
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    for name, content in (('shortlist.md', markdown), ('shortlist.html', page)):
        (directory / name).write_text(content, encoding='utf-8')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('results', nargs='?', type=Path, default=Path('flat-search/results.json'))
    args = parser.parse_args(argv)
    try:
        write(json.loads(args.results.read_text(encoding='utf-8')))
        print('Written flat-search/shortlist.{md,html}')
        return 0
    except (OSError, ValueError, TypeError, KeyError) as error:
        parser.error(str(error))


if __name__ == '__main__':
    main()
