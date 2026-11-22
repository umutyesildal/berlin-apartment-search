# Berlin Apartment Search

A local-first apartment-search skill for Berlin. Search public offers from
InBerlinWohnen and Kleinanzeigen, triage unsuitable ads, and check rental costs
and scam signals. Python 3.9+, standard library only. P2, version 0.3.0.

Features: transparent fit scores; optional cached public-transit/bike estimates;
a local application tracker; factual contact/cover-letter drafts and dossier
readiness checks; escaped Markdown/HTML shortlists; municipal, classifieds,
WG-Gesucht and Wunderflats search. Furnished temporary rentals are tagged, not
treated as equivalent to a normal long-term flat.
One-shot new-listing watch, opt-in self-notifications and offline alert/page
imports are included; blocked portals never trigger a browser bypass.

## What it does

- One-page, read-only search with normalized JSON and Markdown results.
- Conservative duplicate suggestions, noise classification and untrusted-text checks.
- Weighted scam signals and rent/deposit arithmetic, with missing facts left unknown.
- Sourced Berlin guidance on WBS, municipal housing, moving in and newcomers.
- Local data only in gitignored `./flat-search/`; core search needs no account or API key.

This is **orientation, not legal advice**. It neither finds every available flat
nor proves that a listing is safe or its rent lawful. Listings may be stale.

## Install

### Claude Code

```text
/plugin marketplace add umutyesildal/berlin-apartment-search
/plugin install berlin-apartment-search@berlin-apartment-search
```

### Codex and other agents

Open this repository and follow [AGENTS.md](AGENTS.md). The canonical skill is
[SKILL.md](skills/berlin-apartment-search/SKILL.md), also linked under
`.agents/skills/` and `.claude/skills/`. Claude and Codex plugin manifests are
included. For chat-only clients, paste [the starter prompt](docs/chatgpt-prompt.md);
without a local runtime they cannot execute the scripts or persist guard state.
No hosted MCP service is required or shipped.

## Start

Ask: “Help me look for a Berlin apartment.” The agent starts a short setup
interview using [the profile template](skills/berlin-apartment-search/assets/profile.template.yml).
Do not put your identity documents in this repository. Store private files only
in `./flat-search/` and protect that directory on your own machine.

From the repository root:

```bash
python3 skills/berlin-apartment-search/scripts/search.py --source inberlinwohnen
python3 skills/berlin-apartment-search/scripts/search.py --source kleinanzeigen --max-warm 1300 --min-rooms 2
python3 skills/berlin-apartment-search/scripts/search.py --help
```

With no `--source`, the CLI fans out once to all adapters. See
[source methods and limitations](skills/berlin-apartment-search/references/sources.md)
before running. Local filters are not a completeness guarantee: only the first
page is fetched. Unknown rent/room values remain visible for manual review.
Use `--exclude swap,wg,sublet,wanted,furnished,temporary` to hide tagged noise;
the default keeps it visible. YAML is an interview aid; copy
[the JSON profile](skills/berlin-apartment-search/assets/profile.template.json)
to `flat-search/profile.json` for CLI scoring and drafts. CLI arguments control
hard search filters; profile preferences only influence fit.

Results: `flat-search/results.json`, `flat-search/results.md`; guard state:
`flat-search/guard.sqlite`. Source status is always reported, including partial
failures. Exit 0 means all selected sources returned valid results (possibly
empty), 1 means a blocked/deferred/error source, and 2 is invalid CLI input.
Search also writes `flat-search/shortlist.md` and `flat-search/shortlist.html`.
External text is escaped, not trusted instructions. Shortlist links accept HTTPS
only; inspect URLs before opening. The HTML uses no remote assets or scripts.

## P1 local tools

```bash
python3 skills/berlin-apartment-search/scripts/search.py --source wggesucht --profile flat-search/profile.json --weights '{"budget":35}'
python3 skills/berlin-apartment-search/scripts/search.py --source wunderflats
python3 skills/berlin-apartment-search/scripts/report.py flat-search/results.json
python3 skills/berlin-apartment-search/scripts/tracker.py import flat-search/results.json
python3 skills/berlin-apartment-search/scripts/tracker.py list
python3 skills/berlin-apartment-search/scripts/draft.py --profile flat-search/profile.json --ad flat-search/ad.txt --template contact-de-sie
python3 skills/berlin-apartment-search/scripts/dossier.py flat-search/profile.json
python3 skills/berlin-apartment-search/scripts/commute.py --origin "Alexanderplatz Berlin" --to-coordinates 52.5251 13.3694
```

Fit is 0–100 with a reason per factor. Missing inputs stay neutral at 50, so 50
may mean entirely unknown, not medium quality. Scam/rent/integrity flags remain
separate. Default factor weights are at the top of `fit_score.py`; override them
with `--weights` JSON. `value_eur_m2` is an optional user-supplied cold-rent value
benchmark, not a legal determination. Freshness requires an ISO `posted_at` date.

Commute is opt-in: search accepts `--commute-to LAT LON` and
`--commute-mode transit|bike`, using existing listing coordinates only. Public
place geocoding sends the query to Nominatim; routing sends coordinates to
Transitous. Do not send a private home/work address without consent. Requests
are guarded, identifying and cached; Nominatim has a minimum 1-second gap
(normally the longer guard jitter), no autocomplete or bulk mode. `--offline`
on `commute.py` uses cache only. Geocodes cache for 30 days; departure-bucketed
routes for one day. Unknown/offline/deferred never becomes a made-up travel time.
Bike routing requests direct results with the profile's `max_commute_minutes`
(`commute.py --max-minutes`), defaulting to and capped at 90 minutes.

Draft templates: German **Sie** for flats, German **du** for WGs, English and a
German cover letter. Missing facts remain `[PLACEHOLDER]` fields. Output is a
new local file only; verify facts and any extracted code-word before sending
yourself. The draft command refuses overwrites. Dossier checks use issued-date
metadata, not document contents. Three-month SCHUFA freshness is a preparation
heuristic, not a universal legal expiry.

Tracker states: pending → contacted → viewing → applied → offer, with rejected
or dead terminal states. `tracker.py status SOURCE:ID contacted --note "..."`
records only a user-confirmed action. Refetch/import updates source metadata,
not the user's verdict, notes or status. CSV and event history stay private.

## Safety and scope

No portal login, advertiser messages, form filling, retries, CAPTCHA solving,
proxies or stealth. Optional notifications go only to your own private destination.
Each site gets at most 6 requests/hour and 30/day, with 3–7 seconds of jitter
between requests. Blocks persist escalating 15-minute / 1-hour / 3-hour / 12-hour
cooldowns. HTTP 403/429, challenge pages and unrecognized/empty response shapes
are never silently treated as empty inventory. Do not delete guard state to
evade limits. Public access can break; use your own browser when blocked.

You make all contacts and applications yourself.
All implementation is original; no research-project code was copied.

## P2 watch and offline imports

```bash
python3 skills/berlin-apartment-search/scripts/watch.py --source inberlinwohnen --profile flat-search/profile.json --notify ntfy --dry-run
python3 skills/berlin-apartment-search/scripts/alerts.py flat-search/exports/alert.eml
python3 skills/berlin-apartment-search/scripts/import_page.py flat-search/saved/page.html --url https://www.immowelt.de/expose/FICTIONAL-ID
```

Watch runs once, suppresses seen IDs/URLs and conservative cross-portal matches,
scores only new groups and writes `flat-search/watch/results.json` and escaped
shortlists. Durable state lives in `flat-search/watch.sqlite`. `first_seen` is a
local observation (labelled freshness fallback), not a portal publication date.
`notified_at` records a precommitted attempt; `delivery` records the outcome.
At-most-once is deliberate: seen items are never automatically retried after
failures, crashes, disabled notifications or dry runs. A crash between claiming
and writing a report can lose that run's report; inspect state, never erase it
to trigger re-notification. Possible duplicates can be different similar units.

Notifications default off; dry-run sends nothing and needs no credentials but
**does persist seen state**. For real delivery choose `--notify ntfy|telegram`
and `--confirm-self`. Set `NTFY_TOPIC_URL` or `TELEGRAM_BOT_TOKEN` plus
`TELEGRAM_CHAT_ID` only in the environment, never repository/profile/scheduler
files or command-line arguments. Telegram accepts positive private chat IDs,
not groups/channels; ntfy is restricted to HTTPS ntfy.sh topics. Use a private
unguessable topic and understand that its URL is a bearer secret. Messages
contain a count/local-report reminder, not listing text or personal data.

Export saved-search .eml files yourself or save/paste a page from your own
browser. Imports use no network, browser automation, cookies, remote images,
inbox access or attachments. Raw exports and generated files stay private.
Output directories: `flat-search/alerts/` and `flat-search/imported-page/`.
Unrecognized formats are reported, not called valid empty portal inventory.
Imported entries are normalized, deduplicated and assessed as untrusted data;
prices without an explicit basis stay asking rent. Email dates are not posted dates.
Scheduling examples and the recommended **at least two-hour interval** are in
[automation](skills/berlin-apartment-search/references/automation.md); blocked
portal/manual-import guidance is in the [browser recipe](skills/berlin-apartment-search/references/browser-recipe.md).

## Develop

```bash
python3 -m unittest discover -s tests -v
python3 tools/validate_skill.py
```

Tests use synthetic fixtures and deny network access. See [CONTRIBUTING.md](CONTRIBUTING.md),
[SECURITY.md](SECURITY.md) and [MIT license](LICENSE).
