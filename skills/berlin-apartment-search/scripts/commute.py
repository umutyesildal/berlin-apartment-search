"""Optional public geocoding and routes; never send names or private documents."""

import argparse
import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from private_paths import private_directory, private_file
from urllib.parse import urlencode
from guard import Blocked, Deferred, Guard, SourceError


USER_AGENT = 'berlin-apartment-search/0.3.1 (https://github.com/umutyesildal/berlin-apartment-search)'


def coordinates(value):
    if not isinstance(value, (list, tuple)) or len(value) != 2 or any(isinstance(x, bool) for x in value):
        raise ValueError('coordinates must be [latitude, longitude]')
    lat, lon = map(float, value)
    if not math.isfinite(lat) or not math.isfinite(lon) or not (-90 <= lat <= 90 and -180 <= lon <= 180):
        raise ValueError('coordinates outside valid range')
    return [lat, lon]


class Commute:
    def __init__(self, guard, directory='flat-search', offline=False):
        self.guard, self.directory, self.offline = guard, Path(directory) / 'commute-cache', offline

    def cached(self, site, url, ttl):
        key = hashlib.sha256(url.encode()).hexdigest()
        path = self.directory / (key + '.json')
        try:
            cached = json.loads(path.read_text(encoding='utf-8'))
            age = datetime.now(timezone.utc).timestamp() - cached['at']
            if 0 <= age <= ttl:
                return cached['data']
        except (OSError, ValueError, TypeError, KeyError):
            pass
        if self.offline:
            raise SourceError('offline and no fresh cache')
        data = json.loads(self.guard.fetch(site, url, headers={'User-Agent': USER_AGENT, 'Accept': 'application/json'}))
        private_directory(self.directory)
        with private_file(path, encoding='utf-8') as stream:
            stream.write(json.dumps({'at': datetime.now(timezone.utc).timestamp(), 'data': data}))
        return data

    def geocode(self, query):
        if not isinstance(query, str) or not query.strip():
            return {'status': 'unknown', 'reason': 'No geocoding query.'}
        try:
            url = 'https://nominatim.openstreetmap.org/search?' + urlencode(
                {'q': query.strip(), 'format': 'jsonv2', 'limit': 1, 'countrycodes': 'de'})
            data = self.cached('nominatim', url, 30 * 86400)
            if not data:
                return {'status': 'unknown', 'reason': 'No geocoding match.'}
            lat, lon = coordinates([data[0]['lat'], data[0]['lon']])
            return {'status': 'ok', 'latitude': lat, 'longitude': lon,
                    'attribution': '© OpenStreetMap contributors, ODbL; Nominatim. Verify approximate match.'}
        except (Blocked, Deferred, SourceError, OSError, ValueError, KeyError, TypeError, IndexError) as error:
            return {'status': 'unknown', 'reason': str(error)}

    def route(self, origin, destination, mode='transit', at=None, max_minutes=None):
        try:
            start, end = coordinates(origin), coordinates(destination)
            if mode not in ('transit', 'bike'):
                raise ValueError('mode must be transit or bike')
            departure = at or datetime.now(timezone.utc).replace(second=0, microsecond=0)
            if departure.tzinfo is None:
                departure = departure.replace(tzinfo=timezone.utc)
            departure = departure.replace(minute=(departure.minute // 15) * 15)
            params = {'fromPlace': ','.join(map(str, start)), 'toPlace': ','.join(map(str, end)),
                      'directModes': 'BIKE' if mode == 'bike' else 'WALK',
                      'time': departure.isoformat(),
                      'numItineraries': 1}
            if mode == 'bike':
                params['transitModes'] = ''
                maximum = 90 if max_minutes is None else float(max_minutes)
                if isinstance(max_minutes, bool) or not math.isfinite(maximum) or maximum <= 0:
                    raise ValueError('maximum commute duration must be positive and finite')
                params['maxDirectTime'] = max(1, int(min(maximum, 90) * 60))
            data = self.cached('transitous', 'https://api.transitous.org/api/v1/plan?' + urlencode(params), 86400)
            if mode == 'bike':
                itineraries = [item for item in data.get('direct', [])
                               if any(leg.get('mode') == 'BIKE' for leg in item.get('legs', []))
                               and all(leg.get('mode') in ('BIKE', 'WALK') for leg in item.get('legs', []))]
            else:
                itineraries = data.get('itineraries', data.get('plan', {}).get('itineraries', []))
            durations = [float(item['duration']) / 60 for item in itineraries if 'duration' in item]
            durations = [value for value in durations if math.isfinite(value) and value >= 0]
            if not durations:
                return {'status': 'unknown', 'reason': 'No usable itinerary.'}
            return {'status': 'ok', 'minutes': round(min(durations), 1), 'mode': mode,
                    'departure': departure.isoformat(), 'attribution': 'Transitous / MOTIS; verify departure and service.'}
        except (Blocked, Deferred, SourceError, OSError, ValueError, KeyError, TypeError, AttributeError) as error:
            return {'status': 'unknown', 'reason': str(error)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--origin', help='Explicit public address/place to geocode')
    parser.add_argument('--from-coordinates', nargs=2, type=float)
    parser.add_argument('--to-coordinates', nargs=2, type=float, required=True)
    parser.add_argument('--mode', choices=('transit', 'bike'), default='transit')
    parser.add_argument('--max-minutes', type=float, help='Bike route search limit; default and hard cap: 90 minutes')
    parser.add_argument('--offline', action='store_true')
    args = parser.parse_args(argv)
    if bool(args.origin) == bool(args.from_coordinates):
        parser.error('provide exactly one of --origin or --from-coordinates')
    client = Commute(Guard(), offline=args.offline)
    geocoded = client.geocode(args.origin) if args.origin else None
    origin = args.from_coordinates or ([geocoded['latitude'], geocoded['longitude']] if geocoded['status'] == 'ok' else None)
    result = client.route(origin, args.to_coordinates, args.mode, max_minutes=args.max_minutes) if origin else geocoded
    print(json.dumps({'geocode': geocoded, 'route': result}, ensure_ascii=False))
    return 0 if result['status'] == 'ok' else 1


if __name__ == '__main__':
    raise SystemExit(main())
