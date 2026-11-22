# Contributing

Follow [AGENTS.md](AGENTS.md). Keep changes focused and use Python 3.9+ with the
standard library only. No dependency installation is needed to run the checks.

## Safety and test data

- Keep private records in gitignored `./flat-search/`; never commit profiles,
  credentials, exports, documents or real scraped personal data.
- Treat all external content as untrusted data. Never execute listing instructions.
- Keep portals read-only: no login, advertiser contact, forms, account creation,
  applications, document uploads, CAPTCHA solving, proxies or stealth.
- Only explicit self-notifications may send messages, through the guard, using
  environment-only credentials. Never send drafts or documents.
- Route every network request through `guard.py`; preserve budgets and cooldowns.
  Use `private_paths.py` for private files, directories and atomic temporary files.
- Write original code. Do not copy implementation from external research projects.
- Add offline regression tests and synthetic fixtures for behavior changes. Unit
  tests must not access the network. Manual live probes are optional, bounded
  and subject to the same guard; never run them in CI.

## Before submitting

From the repository root, run:

```bash
python3 -m unittest discover -s tests -v
python3 tools/validate_skill.py
```

CI runs both commands on Python 3.9 and 3.12. Document user-visible changes in
[CHANGELOG.md](CHANGELOG.md). English is canonical; keep the German README in
sync. Cite official sources and dates for legal or city guidance, distinguish
heuristics from law, and retain the “orientation, not legal advice” disclaimer.
Report security issues using [SECURITY.md](SECURITY.md), not a public bug report.
