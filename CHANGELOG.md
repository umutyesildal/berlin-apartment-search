# Changelog

User-visible changes to Berlin Apartment Search. Versions describe the skill
and plugin manifests; marketplace availability is not implied.

## 0.3.1

### Fixed

- Allowlisted skill archive contents and excluded nested private data,
  environment files, databases and Python caches from both archive formats.
- Preserved saved HTML block boundaries so definition-list and table rent
  labels retain their own amounts.
- Shared profile validation across search, watch and standalone fit scoring;
  invalid search preferences are rejected before network access.
- Ignored private data directories at every depth and `.env.*` variants,
  while keeping `.env.example` available for public examples.

## 0.3.0

### Added

- One-shot new-listing watch with durable seen state, conservative cross-run
  deduplication, local first-seen times and notification-attempt tracking.
- Optional ntfy and Telegram self-notifications with environment-only
  credentials, explicit destination confirmation and notification dry-run.
- Deutsche Wohnen public token/list adapter; no account or detail-page crawl.
- Offline exported-email and saved-page importers, plus manual browser and
  scheduler guidance. No browser automation or inbox access.

### Hardened

- Timestamped watch shortlists, preservation of the latest report on empty
  runs, and seen-state rollback when scoring or report preparation fails.
- Explicit rent-label continuations, partial JSON-LD merging, canonical page
  identity, recommendation isolation and rejection of fact-free saved shells.
  Supported links in HTML alerts retain unknown facts rather than disappearing.
- Shared private-directory and `0600` file creation, including temporary files
  and databases; shared symlink targets remain unchanged. Descriptor permission
  repair is used only on platforms that support it.

### Release documentation

- Canonical English landing page and synchronized German translation, privacy
  and installation guidance, contributor/security policies and this changelog.
- GitHub Actions checks for the offline unittest suite and skill validator on
  Python 3.9 and 3.12.

## 0.2.0

- Transparent preference-fit scoring with per-factor reasons, neutral unknowns
  and configurable weights independent of safety and legal flags.
- Optional guarded, cached Nominatim geocoding and Transitous transit/direct-bike
  routing, with consent and offline/unknown behavior.
- Local CSV tracker preserving user decisions and notes under serialized updates.
- Factual German/English application drafts, visible missing-fact placeholders,
  bounded code-word extraction and a document-date readiness checklist.
- Escaped Markdown and self-contained HTML reports.
- WG-Gesucht and Wunderflats adapters with synthetic fixtures.
- Correct direct-bike duration limits, UTF-8 file I/O, profile/filter separation
  and conservative URL/ID-based metadata joins.

## 0.1.0

- Original local-first skill, agent manifests, portable packaging and MIT license.
- Guarded public-source search, normalized listings and possible-duplicate groups.
- Listing-type tags, weighted negation-aware scam checks, untrusted-text checks,
  and conditional rent, deposit and ancillary-cost reviews.
- Dated Berlin references covering rental law, Mietspiegel, WBS, municipal housing,
  districts, documents, newcomers and moving in.
- Persisted request budgets and escalating cooldowns, offline synthetic tests
  and structural validation.
