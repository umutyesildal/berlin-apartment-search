"""Explicit opt-in notifications to a user-confirmed private destination only."""

import argparse
import json
import os
import re
from urllib.parse import urlsplit
from guard import Blocked, Deferred, Guard, SourceError


def destination(provider, confirm_self=False, environ=None):
    if not confirm_self:
        raise ValueError('Real delivery requires --confirm-self: destination belongs only to you.')
    env = os.environ if environ is None else environ
    if provider == 'ntfy':
        url = env.get('NTFY_TOPIC_URL', '')
        parsed = urlsplit(url)
        if (parsed.scheme != 'https' or parsed.netloc != 'ntfy.sh' or parsed.query or parsed.fragment
                or not re.fullmatch(r'/[A-Za-z0-9_-]{1,128}', parsed.path)):
            raise ValueError('NTFY_TOPIC_URL must be a private HTTPS ntfy.sh topic URL; value omitted.')
        return url, None
    if provider == 'telegram':
        token, chat = env.get('TELEGRAM_BOT_TOKEN', ''), env.get('TELEGRAM_CHAT_ID', '')
        if not re.fullmatch(r'\d+:[A-Za-z0-9_-]+', token) or not re.fullmatch(r'[1-9]\d*', chat):
            raise ValueError('Telegram requires bot token and positive private chat id from environment; values omitted.')
        return 'https://api.telegram.org/bot' + token + '/sendMessage', chat
    raise ValueError('unknown notification provider')


def send(guard, provider, message, dry_run=False, confirm_self=False, environ=None):
    if provider not in ('ntfy', 'telegram') or not isinstance(message, str) or not message.strip() or len(message) > 3000:
        raise ValueError('provider/message invalid; message must contain 1–3000 characters')
    if dry_run:
        return {'provider': provider, 'status': 'dry_run', 'characters': len(message)}
    url, chat = destination(provider, confirm_self, environ)
    body = message.encode('utf-8') if provider == 'ntfy' else json.dumps(
        {'chat_id': chat, 'text': message, 'disable_web_page_preview': True}).encode('utf-8')
    headers = {'Content-Type': 'text/plain; charset=utf-8' if provider == 'ntfy' else 'application/json'}
    try:
        data = json.loads(guard.fetch(provider, url, headers=headers, body=body))
        ok = isinstance(data, dict) and (data.get('ok') is True if provider == 'telegram' else bool(data.get('id')))
        return {'provider': provider, 'status': 'sent' if ok else 'failed',
                'reason': 'accepted by service' if ok else 'service did not acknowledge delivery'}
    except (Blocked, Deferred, SourceError, OSError, ValueError, TypeError):
        return {'provider': provider, 'status': 'failed', 'reason': 'guard/network/service failure; no automatic retry'}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--provider', choices=('ntfy', 'telegram'), required=True)
    parser.add_argument('--message', required=True)
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--confirm-self', action='store_true')
    args = parser.parse_args(argv)
    try:
        result = send(Guard(), args.provider, args.message, args.dry_run, args.confirm_self)
        print(json.dumps(result))
        return 1 if result['status'] == 'failed' else 0
    except (OSError, ValueError):
        parser.error('Notification configuration invalid; secrets omitted.')


if __name__ == '__main__':
    raise SystemExit(main())
