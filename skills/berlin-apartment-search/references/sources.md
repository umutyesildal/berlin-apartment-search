# Sources and access

Data-as-of: 2026-11-22. **Orientation, not legal advice.**

All adapters are original, read-only implementations. No account, cookies,
messaging or detail-page crawl. One request per selected source per invocation,
page one only, no automatic retries. Public data can be incomplete or stale.

| CLI source | Mechanism | Limitations |
|---|---|---|
| `inberlinwohnen` | GET `https://www.inberlinwohnen.de/wohnungsfinder/?page=1`; decode HTML `wire:snapshot` attributes, unwrap Livewire array markers, read `data.item` | Municipal-company feed; local filters only; no full-inventory claim |
| `kleinanzeigen` | GET `https://www.kleinanzeigen.de/s-wohnung-mieten/berlin/c203l3331`; parse public `article[data-adid]` cards and optional JSON-LD | Asking-price basis often ambiguous; preserve price without inventing cold/warm rent; local filters |
| `immoscout` | ImmoScout24 anonymous POST `https://api.mobile.immobilienscout24.de/search/list`, JSON body `{"supportedResultListTypes":[],"userData":{}}`, Accept/Content-Type JSON, app User-Agent `ImmoScout_28.9_27.2_._`; Berlin region geocodes `/de/berlin/berlin`, `realestatetype=apartmentrent`, page 1 | Included by default, no separate opt-in; API may change |

ToS note: ImmoScout24's mobile API use may conflict with its terms; review them before use: https://www.immobilienscout24.de/agb.html

The mobile query maps CLI `--max-warm` to `price=-N` with
`pricetype=calculatedtotalrent`, `--min-rooms` to `numberofrooms=N-`, and sorts
`-firstactivation`; website URLs are not accepted. Local filters apply again to
all normalized records, keeping unknowns for review. No arbitrary URL fetching.

Default HTML User-Agent is transparent: `berlin-apartment-search/0.1.0`.
HTTPS only; fixed adapter endpoints; automatic redirects and environment proxies
disabled; 30-second timeout and 5 MiB response cap. Unexpected redirects/errors
are reported, not followed. The app User-Agent above is the sole protocol-specific
exception, not a browser stealth scheme.

Budgets per source are 6 requests in a rolling hour and 30 in a rolling day,
persisted in `flat-search/guard.sqlite`. Every attempted request is charged;
concurrent CLI invocations serialize budget reservations. A 3–7 second random
minimum gap is enforced after a prior request. 403/429 and recognized bot walls
trigger 15min/1h/3h/12h escalating cooldowns, retained across restarts. Empty or
unrecognized page shapes are conservatively blocked, not valid zero results;
explicit zero-result markers are accepted. Parse drift in a recognized populated
shape is reported as an error. Do not reset state to work around a block.

Normalized fields include source identity, title, URL, district, PLZ/street,
rooms, area, cold/warm/asking rent, costs, deposit, WBS, dates, coordinates, text
and heuristic type tags. Missing values stay null. Search-card data does not
support all fields. Possible duplicate clusters preserve all member listings.
No cross-run “new listing” tracker or watch mode is implemented in P0.

Other portals, including Immowelt, are not polled in P0. Use your own browser or
saved alerts if access fails; do not escalate to a bypass. Official portal entry
points (2026): https://www.inberlinwohnen.de/wohnungsfinder/ and
https://www.kleinanzeigen.de/s-wohnung-mieten/berlin/c203l3331
