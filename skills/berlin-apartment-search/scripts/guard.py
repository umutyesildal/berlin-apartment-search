"""Persisted request accounting; no retries, redirects, proxy or cookie state."""

import json
import random
import re
import sqlite3
import time
from contextlib import contextmanager
from http.client import HTTPException
from pathlib import Path
from private_paths import private_directory
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener


class Blocked(RuntimeError):
    pass


class Deferred(RuntimeError):
    pass


class SourceError(RuntimeError):
    pass


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class Guard:
    HOURLY = 6
    DAILY = 30
    COOLDOWNS = (900, 3600, 10800, 43200)

    def __init__(self, directory='flat-search', clock=time.time, sleep=time.sleep, jitter=None):
        directory = Path(directory)
        private_directory(directory)
        self.path = directory / 'guard.sqlite'
        self.clock, self.sleep = clock, sleep
        self.jitter = jitter or (lambda: random.uniform(3, 7))
        with self.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS requests (site TEXT, at REAL)')
            db.execute('CREATE TABLE IF NOT EXISTS blocks (site TEXT PRIMARY KEY, strikes INTEGER, until REAL)')

    @contextmanager
    def connect(self):
        connection = sqlite3.connect(str(self.path), timeout=30)
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def reserve(self, site):
        now = self.clock()
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            block = db.execute('SELECT until FROM blocks WHERE site=?', (site,)).fetchone()
            if block and block[0] > now:
                raise Deferred('cooldown until ' + str(int(block[0])))
            db.execute('DELETE FROM requests WHERE at < ?', (now - 86400,))
            daily, hourly, last = db.execute(
                'SELECT COUNT(*), COALESCE(SUM(at > ?),0), MAX(at) FROM requests WHERE site=?',
                (now - 3600, site)).fetchone()
            if daily >= self.DAILY or hourly >= self.HOURLY:
                raise Deferred('persisted request budget exhausted')
            gap = max(1.0, self.jitter()) if site == 'nominatim' else self.jitter()
            when = max(now, last + gap) if last is not None else now
            db.execute('INSERT INTO requests VALUES (?,?)', (site, when))
        if when > now:
            self.sleep(when - now)
            with self.connect() as db:
                block = db.execute('SELECT until FROM blocks WHERE site=?', (site,)).fetchone()
            if block and block[0] > self.clock():
                raise Deferred('cooldown until ' + str(int(block[0])))

    def block(self, site, reason):
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT strikes FROM blocks WHERE site=?', (site,)).fetchone()
            strikes = row[0] + 1 if row else 1
            until = self.clock() + self.COOLDOWNS[min(strikes - 1, len(self.COOLDOWNS) - 1)]
            db.execute('INSERT OR REPLACE INTO blocks VALUES (?,?,?)', (site, strikes, until))
        raise Blocked(reason + '; cooldown until ' + str(int(until)))

    def fetch(self, site, url, headers=None, body=None):
        parsed = urlsplit(url)
        hosts = {'inberlinwohnen': 'www.inberlinwohnen.de',
                 'kleinanzeigen': 'www.kleinanzeigen.de',
                 'immoscout': 'api.mobile.immobilienscout24.de',
                 'wggesucht': 'www.wg-gesucht.de', 'wunderflats': 'wunderflats.com',
                 'deutschewohnen': 'www.deutsche-wohnen.com',
                 'ntfy': 'ntfy.sh', 'telegram': 'api.telegram.org',
                 'nominatim': 'nominatim.openstreetmap.org', 'transitous': 'api.transitous.org'}
        if parsed.scheme != 'https' or parsed.hostname != hosts.get(site) or parsed.port not in (None, 443):
            raise SourceError('endpoint not permitted')
        if parsed.username or parsed.password:
            raise SourceError('URL credentials not permitted')
        if site in ('ntfy', 'telegram'):
            path_pattern = r'/[A-Za-z0-9_-]{1,128}' if site == 'ntfy' else r'/bot\d+:[A-Za-z0-9_-]+/sendMessage'
            if body is None or parsed.query or parsed.fragment or not re.fullmatch(path_pattern, parsed.path):
                raise SourceError('notification endpoint not permitted')
        self.reserve(site)
        request_headers = {'User-Agent': 'berlin-apartment-search/0.3.0',
                           'Accept': 'text/html,application/json', 'Accept-Encoding': 'identity'}
        request_headers.update(headers or {})
        request = Request(url, data=body, headers=request_headers)
        opener = build_opener(ProxyHandler({}), NoRedirect())
        try:
            with opener.open(request, timeout=30) as response:
                raw = response.read(5 * 1024 * 1024 + 1)
                if len(raw) > 5 * 1024 * 1024:
                    raise SourceError('response exceeds 5 MiB')
                text = raw.decode('utf-8', errors='replace')
        except HTTPError as error:
            if error.code in (403, 429):
                self.block(site, 'HTTP ' + str(error.code))
            raise SourceError('HTTP ' + str(error.code)) from error
        except (URLError, TimeoutError, OSError, HTTPException) as error:
            raise SourceError('network failure: ' + type(error).__name__) from error
        self.check_body(site, text)
        return text

    def check_body(self, site, text):
        lower = text.lower()
        markers = ('<title>access denied', '<title>just a moment', 'verify you are human',
                   'ich bin kein roboter', 'unusual traffic', 'cf-chl-', 'datadome',
                   'captcha-delivery.com', 'g-recaptcha', 'hcaptcha-container')
        if (not text.strip() or any(marker in lower for marker in markers)
                or re.search(r'<title>[^<]*(?:captcha|robot|zugriff verweigert)', lower)):
            self.block(site, 'empty response or challenge page')


if __name__ == '__main__':
    print(json.dumps({'hourly': Guard.HOURLY, 'daily': Guard.DAILY,
                      'cooldowns_seconds': Guard.COOLDOWNS}))
