"""One search, durable seen-state claims, new-only local report, then optional delivery."""

import argparse
import json
import sqlite3
from dataclasses import fields
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit
from classify import PATTERNS
from dedupe import possible_match
from fit_score import weights_from
from guard import Guard
from models import Listing
from notify import destination, send
from search import SOURCES, collect, enrich, positive, write_report


def aliases(member):
    result = ['id:' + member['id']]
    parsed = urlsplit(member.get('url') or '')
    if parsed.scheme == 'https' and parsed.hostname:
        result.append('url:' + urlunsplit((parsed.scheme, parsed.netloc.casefold(), parsed.path, '', '')))
    return result


def as_listing(member):
    return Listing(**{field.name: member[field.name] for field in fields(Listing) if field.name in member})


def claim_new(report, path, notification=False, dry_run=False, now=None):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    at = now or datetime.now(timezone.utc).isoformat()
    connection = sqlite3.connect(str(path), timeout=30)
    new_groups, claimed = [], []
    try:
        with connection as db:
            db.execute('CREATE TABLE IF NOT EXISTS seen (id TEXT PRIMARY KEY, first_seen TEXT NOT NULL, notified_at TEXT, payload TEXT NOT NULL, delivery TEXT NOT NULL)')
            db.execute('CREATE TABLE IF NOT EXISTS aliases (alias TEXT PRIMARY KEY, id TEXT NOT NULL)')
            db.execute('BEGIN IMMEDIATE')
            known = [(row[0], json.loads(row[1])) for row in db.execute('SELECT id,payload FROM seen')]
            for cluster in report['groups']:
                members = cluster['members']
                previous = None
                for member in members:
                    for alias in aliases(member):
                        match = db.execute('SELECT id FROM aliases WHERE alias=?', (alias,)).fetchone()
                        if match:
                            previous = match[0]
                            break
                    if previous:
                        break
                    previous = next((identifier for identifier, saved in known
                                     if possible_match(as_listing(member), as_listing(saved))), None)
                    if previous:
                        break
                identifier = previous or members[0]['id']
                if previous is None:
                    notified_at = at if notification and not dry_run else None
                    delivery = 'attempted' if notified_at else 'dry_run' if notification else 'disabled'
                    for member in members:
                        member.update(first_seen=at, notified_at=notified_at)
                    db.execute('INSERT INTO seen VALUES (?,?,?,?,?,?)',
                               (identifier, at, notified_at, json.dumps(members[0]), delivery))
                    known.append((identifier, members[0]))
                    claimed.append(identifier)
                    new_groups.append(cluster)
                for member in members:
                    for alias in aliases(member):
                        db.execute('INSERT OR IGNORE INTO aliases VALUES (?,?)', (alias, identifier))
    finally:
        connection.close()
    result = dict(report, groups=new_groups, listing_count=sum(len(group['members']) for group in new_groups),
                  new_count=len(new_groups), seen_suppressed=report['listing_count'] - sum(len(group['members']) for group in new_groups))
    return result, claimed


def run(selected, guard, directory='flat-search', profile=None, weights=None, max_warm=None, min_rooms=None,
        exclude=(), provider=None, dry_run=False, confirm_self=False):
    if provider and not dry_run:
        destination(provider, confirm_self)
    profile = dict(profile or {})
    if max_warm is not None:
        profile['max_warm_eur'] = max_warm
    if min_rooms is not None:
        profile['min_rooms'] = min_rooms
    report = collect(selected, guard, max_warm, min_rooms, exclude, profile, weights, assess=False)
    path = Path(directory) / 'watch.sqlite'
    report, claimed = claim_new(report, path, bool(provider), dry_run)
    enrich(report, profile, weights)
    report['notification'] = {'status': 'disabled' if provider is None else 'no_new'}
    write_report(report, Path(directory) / 'watch')
    if provider and claimed:
        receipt = send(guard, provider, 'New apartment listings: %d. Review your local flat-search/watch/shortlist.html. No safety guarantee.'
                       % len(claimed), dry_run, confirm_self)
        report['notification'] = receipt
        with sqlite3.connect(str(path)) as db:
            db.executemany('UPDATE seen SET delivery=? WHERE id=?', [(receipt['status'], identifier) for identifier in claimed])
        write_report(report, Path(directory) / 'watch')
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', choices=tuple(SOURCES), action='append')
    parser.add_argument('--profile', type=Path)
    parser.add_argument('--weights', default='{}')
    parser.add_argument('--max-warm', type=positive)
    parser.add_argument('--min-rooms', type=positive)
    parser.add_argument('--exclude', default='')
    parser.add_argument('--notify', choices=('ntfy', 'telegram'))
    parser.add_argument('--dry-run', action='store_true', help='Only notification delivery is dry-run; seen state is persisted')
    parser.add_argument('--confirm-self', action='store_true')
    args = parser.parse_args(argv)
    try:
        profile = json.loads(args.profile.read_text()) if args.profile else {}
        weights = weights_from(json.loads(args.weights))
        exclude = set(filter(None, args.exclude.split(',')))
        if not isinstance(profile, dict) or exclude.difference(PATTERNS):
            raise ValueError('profile or exclusion tags invalid')
        report = run(list(dict.fromkeys(args.source or SOURCES)), Guard(), profile=profile, weights=weights,
                     max_warm=args.max_warm, min_rooms=args.min_rooms, exclude=exclude, provider=args.notify,
                     dry_run=args.dry_run, confirm_self=args.confirm_self)
        print(json.dumps({'sources': report['sources'], 'new_count': report['new_count'],
                          'listing_count': report['listing_count'], 'seen_suppressed': report['seen_suppressed'],
                          'notification': report['notification'], 'output': 'flat-search/watch/shortlist.{md,html}'}, ensure_ascii=False))
        return 0 if all(source['status'] == 'ok' for source in report['sources'].values()) and report['notification']['status'] != 'failed' else 1
    except (OSError, ValueError, TypeError, KeyError, sqlite3.Error):
        parser.error('Watch state/configuration/output error; no automatic retry. Private values omitted.')


if __name__ == '__main__':
    raise SystemExit(main())
