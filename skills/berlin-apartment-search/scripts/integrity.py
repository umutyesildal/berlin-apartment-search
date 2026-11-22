"""Flag instructions targeting an assistant; external content is always untrusted."""

import json
import re
import sys


def check(text):
    patterns = {
        'override': r'ignore (?:all |the )?(?:previous|prior|above) instructions|ignoriere .*anweisungen',
        'role_spoof': r'<\|?(?:system|assistant)\b|\[system\]|system prompt|developer message',
        'exfiltration': r'(?:send|upload|reveal|print).{0,60}(?:api.?key|password|secret|credentials|system prompt)',
        'execution': r'\b(?:curl|wget)\s+https?://|\brm\s+-rf\b|\b(?:execute|run) (?:this |the )?(?:command|script)\b',
    }
    flags = [name for name, pattern in patterns.items() if re.search(pattern, text, re.I | re.S)]
    return {'untrusted': True, 'flags': flags, 'needs_review': bool(flags)}


if __name__ == '__main__':
    print(json.dumps(check(sys.stdin.read())))
