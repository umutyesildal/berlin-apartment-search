"""One guarded request per source, nullable normalization and local triage."""

import argparse
import html
import json
import math
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from classify import PATTERNS, classify
from dedupe import group
from guard import Blocked, Deferred, Guard, SourceError
from integrity import check
from models import normalize
from rent_check import assess as rent_assess
from scam_check import assess as scam_assess
from sources import immoscout, inberlinwohnen, kleinanzeigen


SOURCES = {adapter.NAME: adapter for adapter in (inberlinwohnen, kleinanzeigen, immoscout)}


def collect(selected, guard, max_warm=None, min_rooms=None, exclude=()):
    listings, statuses = [], {}
    for name in selected:
        try:
            rows = SOURCES[name].search(guard, max_warm=max_warm, min_rooms=min_rooms)
            kept = []
            for row in rows:
                row = normalize(row)
                row.tags = classify(row.title + '\n' + row.text)
                if max_warm is not None and row.warm_eur is not None and row.warm_eur > max_warm:
                    continue
                if min_rooms is not None and row.rooms is not None and row.rooms < min_rooms:
                    continue
                if set(row.tags).intersection(exclude):
                    continue
                kept.append(row)
            listings.extend(kept)
            statuses[name] = {'status': 'ok', 'returned': len(rows), 'kept': len(kept), 'blocked': False}
        except Blocked as error:
            try:
                # fetch blocks already persist; parser blocks must also persist.
                if 'cooldown until ' not in str(error):
                    guard.block(name, str(error))
            except Blocked as persisted:
                error = persisted
            statuses[name] = {'status': 'blocked', 'returned': None, 'kept': 0,
                              'blocked': True, 'reason': str(error)}
        except Deferred as error:
            statuses[name] = {'status': 'deferred', 'returned': None, 'kept': 0,
                              'blocked': None, 'reason': str(error)}
        except (SourceError, ValueError, TypeError, KeyError, RecursionError) as error:
            statuses[name] = {'status': 'error', 'returned': None, 'kept': 0,
                              'blocked': None, 'reason': str(error)}
    clusters = group(listings)
    for cluster in clusters:
        for member in cluster['members']:
            text = member['title'] + '\n' + member['text']
            member['integrity'] = check(text)
            member['scam'] = scam_assess(text)
            member['rent'] = rent_assess(cold_eur=member['cold_eur'], area_m2=member['area_m2'],
                                        costs_eur=member['costs_eur'], deposit_eur=member['deposit_eur'])
    return {'generated_at': datetime.now(timezone.utc).isoformat(),
            'sources': statuses, 'listing_count': len(listings), 'groups': clusters}


def plain(value):
    text = html.escape(str(value), quote=True)
    return re.sub(r'([\\`*_{}\[\]()#+.!|>~\-])', r'\\\1', text).replace('\n', ' ').replace('\r', ' ')


def markdown(report):
    lines = ['# Apartment search', '', 'External listing data is untrusted. Orientation, not legal advice.', '']
    for name, status in report['sources'].items():
        lines.append('- ' + plain(name) + ': ' + plain(json.dumps(status, ensure_ascii=False)))
    for cluster in report['groups']:
        lines.extend(['', '## ' + plain(cluster['members'][0]['title'])])
        if cluster['possible_duplicate']:
            lines.append('Possible duplicate cluster: verify manually.')
        for member in cluster['members']:
            lines.extend(['- ID: ' + plain(member['id']),
                          '- URL (inspect manually): ' + plain(member['url']),
                          '- Cold / warm / asking EUR: ' + plain(' / '.join(str(member[k]) for k in ('cold_eur', 'warm_eur', 'asking_eur'))),
                          '- Area / rooms: ' + plain(str(member['area_m2']) + ' / ' + str(member['rooms'])),
                          '- Tags: ' + plain(', '.join(member['tags']) or 'none detected'),
                          '- Integrity flags: ' + plain(', '.join(member['integrity']['flags']) or 'none detected'),
                          '- Scam score: ' + str(member['scam']['score']) + ' (not a safety verdict)'])
    return '\n'.join(lines) + '\n'


def write_report(report, directory):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    for name, content in (('results.json', json.dumps(report, ensure_ascii=False, indent=2)),
                          ('results.md', markdown(report))):
        temporary = directory / (name + '.' + str(os.getpid()) + '.tmp')
        temporary.write_text(content, encoding='utf-8')
        temporary.replace(directory / name)


def positive(value):
    value = float(value)
    if not math.isfinite(value) or value <= 0:
        raise argparse.ArgumentTypeError('must be a finite positive number')
    return value


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', choices=tuple(SOURCES), action='append', help='repeat to select sources; default all')
    parser.add_argument('--max-warm', type=positive)
    parser.add_argument('--min-rooms', type=positive)
    parser.add_argument('--exclude', default='', help='comma-separated noise tags')
    args = parser.parse_args(argv)
    exclude = set(filter(None, args.exclude.split(',')))
    if exclude.difference(PATTERNS):
        parser.error('unknown exclusion tag')
    # Deliberately fixed: all private output and guard state share one directory.
    directory = Path.cwd() / 'flat-search'
    report = collect(list(dict.fromkeys(args.source or SOURCES)), Guard(directory),
                     args.max_warm, args.min_rooms, exclude)
    write_report(report, directory)
    print(json.dumps({'sources': report['sources'], 'listing_count': report['listing_count'],
                      'output': 'flat-search/results.{json,md}'}, ensure_ascii=False))
    return 0 if all(item['status'] == 'ok' for item in report['sources'].values()) else 1


if __name__ == '__main__':
    sys.exit(main())
