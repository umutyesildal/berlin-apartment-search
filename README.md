# Berlin Apartment Search

A local-first apartment-search skill for Berlin. Search public offers from
InBerlinWohnen and Kleinanzeigen, triage unsuitable ads, and check rental costs
and scam signals. Python 3.9+, standard library only. P0, version 0.1.0.

## What it does

- One-page, read-only search with normalized JSON and Markdown results.
- Conservative duplicate suggestions, noise classification and untrusted-text checks.
- Weighted scam signals and rent/deposit arithmetic, with missing facts left unknown.
- Sourced Berlin guidance on WBS, municipal housing, moving in and newcomers.
- Local data only in gitignored `./flat-search/`; no accounts or API keys needed.

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

With no `--source`, the CLI fans out once to all P0 adapters. See
[source methods and limitations](skills/berlin-apartment-search/references/sources.md)
before running. Local filters are not a completeness guarantee: only the first
page is fetched. Unknown rent/room values remain visible for manual review.
Use `--exclude swap,wg,sublet,wanted,furnished,temporary` to hide tagged noise;
the default keeps it visible. The profile is an interview aid, not parsed YAML.
CLI arguments control search filters.

Results: `flat-search/results.json`, `flat-search/results.md`; guard state:
`flat-search/guard.sqlite`. Source status is always reported, including partial
failures. Exit 0 means all selected sources returned valid results (possibly
empty), 1 means a blocked/deferred/error source, and 2 is invalid CLI input.
Markdown deliberately renders external text as escaped plain text, not trusted
instructions or embedded links. Open URLs manually after inspection.

## Safety and scope

No login, messages, form filling, retries, CAPTCHA solving, proxies or stealth.
Each site gets at most 6 requests/hour and 30/day, with 3–7 seconds of jitter
between requests. Blocks persist escalating 15-minute / 1-hour / 3-hour / 12-hour
cooldowns. HTTP 403/429, challenge pages and unrecognized/empty response shapes
are never silently treated as empty inventory. Do not delete guard state to
evade limits. Public access can break; use your own browser when blocked.

P1/P2 application drafting, tracker, commute scoring, scheduling, alert ingestion
and additional sources are not implemented. You make all applications yourself.
All implementation is original; no research-project code was copied.

## Develop

```bash
python3 -m unittest discover -s tests -v
python3 tools/validate_skill.py
```

Tests use synthetic fixtures and deny network access. See [CONTRIBUTING.md](CONTRIBUTING.md),
[SECURITY.md](SECURITY.md) and [MIT license](LICENSE).
