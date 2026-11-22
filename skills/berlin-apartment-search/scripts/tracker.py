"""Local CSV tracker and append-only event history; never contacts advertisers."""

import argparse
import csv
import io
import json
import os
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from functools import wraps
from pathlib import Path
from private_paths import private_directory, private_file


FIELDS = ['id', 'date_added', 'last_seen', 'title', 'source', 'url', 'status', 'score', 'verdict', 'notes']
TRANSITIONS = {'pending': {'contacted', 'rejected', 'dead'}, 'contacted': {'viewing', 'rejected', 'dead'},
               'viewing': {'applied', 'rejected', 'dead'}, 'applied': {'offer', 'rejected', 'dead'},
               'offer': {'rejected', 'dead'}, 'rejected': set(), 'dead': set()}


def read_rows(path):
    path = Path(path)
    if not path.exists():
        return []
    with path.open(encoding='utf-8', newline='') as stream:
        rows = list(csv.DictReader(stream))
    for row in rows:
        if row.pop('_encoding', '') == 'spreadsheet-v1':
            for key in row:
                if row[key] and row[key].startswith("'"):
                    row[key] = row[key][1:]
    return rows


def write_rows(path, rows):
    path = Path(path)
    private_directory(path.parent)
    output = io.StringIO(newline='')
    writer = csv.DictWriter(output, FIELDS + ['_encoding'])
    writer.writeheader()
    for row in rows:
        encoded = {}
        for key in FIELDS:
            value = '' if row.get(key) is None else str(row.get(key, ''))
            unsafe = value.startswith(("'", '\t', '\r', '\n')) or value.lstrip().startswith(('=', '+', '-', '@'))
            encoded[key] = "'" + value if unsafe else value
        writer.writerow(dict(encoded, _encoding='spreadsheet-v1'))
    temporary = path.with_name(path.name + '.' + str(os.getpid()) + '.tmp')
    with private_file(temporary, encoding='utf-8') as stream:
        stream.write(output.getvalue())
    temporary.replace(path)


def serialized(operation):
    @wraps(operation)
    def locked(path, *args, **kwargs):
        path = Path(path)
        private_directory(path.parent)
        lock_path = str(path) + '.lock.sqlite'
        with private_file(lock_path, 'a', encoding='utf-8'):
            pass
        with closing(sqlite3.connect(lock_path, timeout=30)) as db:
            with db:
                db.execute('BEGIN IMMEDIATE')
                return operation(path, *args, **kwargs)
    return locked


@serialized
def upsert(path, listings):
    rows = read_rows(path)
    by_id = {row['id']: row for row in rows}
    now = datetime.now(timezone.utc).isoformat()
    for listing in listings:
        identifier = listing.get('id')
        if not isinstance(identifier, str) or not identifier.strip():
            raise ValueError('listing needs a stable source:id')
        if identifier not in by_id:
            row = dict.fromkeys(FIELDS, '')
            row.update(id=identifier, date_added=now, status='pending')
            rows.append(row)
            by_id[identifier] = row
        row = by_id[identifier]
        row.update(last_seen=now)
        for field in ('title', 'source', 'url'):
            row[field] = listing.get(field) or ''
        row['score'] = (listing.get('fit') or {}).get('score', '')
    write_rows(path, rows)
    return rows


@serialized
def update(path, identifier, status=None, note=None, verdict=None):
    rows = read_rows(path)
    row = next((item for item in rows if item['id'] == identifier), None)
    if row is None:
        raise ValueError('unknown tracked listing')
    if status is not None and status != row['status']:
        if status not in TRANSITIONS.get(row['status'], set()):
            raise ValueError('invalid transition: ' + row['status'] + ' → ' + status)
        row['status'] = status
    if note is not None:
        row['notes'] = '\n'.join(filter(None, (row.get('notes'), note)))
    if verdict is not None:
        row['verdict'] = verdict
    write_rows(path, rows)
    event = {'id': identifier, 'at': datetime.now(timezone.utc).isoformat(),
             'status': row['status'], 'note': note, 'verdict': verdict}
    with private_file(Path(path).parent / 'events.jsonl', 'a', encoding='utf-8') as stream:
        stream.write(json.dumps(event, ensure_ascii=False) + '\n')
    return row


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    add = sub.add_parser('import')
    add.add_argument('results', type=Path)
    sub.add_parser('list')
    status = sub.add_parser('status')
    status.add_argument('id')
    status.add_argument('state', choices=tuple(TRANSITIONS))
    status.add_argument('--note')
    status.add_argument('--verdict')
    note = sub.add_parser('note')
    note.add_argument('id')
    note.add_argument('--note', required=True)
    note.add_argument('--verdict')
    args = parser.parse_args(argv)
    path = Path('flat-search/tracker.csv')
    try:
        if args.command == 'import':
            report = json.loads(args.results.read_text(encoding='utf-8'))
            result = upsert(path, [member for group in report['groups'] for member in group['members']])
        elif args.command == 'list':
            result = read_rows(path)
        else:
            result = update(path, args.id, getattr(args, 'state', None), args.note, args.verdict)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError, TypeError, KeyError, csv.Error, sqlite3.Error) as error:
        parser.error(str(error))


if __name__ == '__main__':
    main()
