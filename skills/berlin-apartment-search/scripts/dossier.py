"""Document readiness metadata only; never reads or transmits document contents."""

import argparse
import calendar
import json
from datetime import date
from pathlib import Path


def months_before(day, months):
    year, month = divmod(day.year * 12 + day.month - 1 - months, 12)
    return date(year, month + 1, min(day.day, calendar.monthrange(year, month + 1)[1]))


def checklist(profile, today=None):
    today = today or date.today()
    documents = profile.get('documents') or {}
    output = []
    for key in ('schufa', 'payslips', 'identity', 'wbs'):
        values = documents.get(key) or []
        if not isinstance(values, list):
            raise ValueError('document entries must be lists of date metadata')
        ages, valid, periods = [], [], set()
        for entry in values:
            try:
                issued = date.fromisoformat(entry['issued_on'])
            except (ValueError, TypeError, KeyError):
                ages.append(None)
                continue
            ages.append((today - issued).days)
            if issued <= today:
                valid.append(issued)
                if key == 'payslips':
                    try:
                        period = date.fromisoformat(entry['period'] + '-01')
                        periods.add(period.strftime('%Y-%m'))
                    except (ValueError, TypeError, KeyError):
                        pass
        if key == 'schufa':
            ready = any(day >= months_before(today, 3) for day in valid)
            reason = 'Requested heuristic: issued within 3 calendar months; not a statutory expiry.'
        elif key == 'payslips':
            required = {months_before(today.replace(day=1), offset).strftime('%Y-%m') for offset in (1, 2, 3)}
            ready = required.issubset(periods)
            reason = 'Last 3 completed payroll months: ' + ', '.join(sorted(required)) + '; alternatives may be accepted.'
        else:
            ready = None
            reason = 'Verify validity and whether required; metadata alone does not establish readiness.'
        output.append({'document': key, 'ready': ready, 'ages_days': ages, 'reason': reason})
    return {'as_of': today.isoformat(), 'documents': output,
            'warning': 'Orientation, not legal advice. Do not send a full dossier with an initial enquiry.'}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('profile', type=Path)
    args = parser.parse_args(argv)
    try:
        print(json.dumps(checklist(json.loads(args.profile.read_text(encoding='utf-8'))), ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError, TypeError, AttributeError) as error:
        parser.error(str(error))


if __name__ == '__main__':
    main()
