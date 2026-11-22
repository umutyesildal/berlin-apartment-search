# Sources and access

Data-as-of: 2026-11-22. **Orientation, not legal advice.**

All adapters are original, read-only implementations. No account, cookies,
advertiser messaging or detail-page crawl. One request per selected source per
invocation (two for Deutsche Wohnen), page one only, no automatic retries.
Public data can be incomplete or stale.

| CLI source | Mechanism | Limitations |
|---|---|---|
| `inberlinwohnen` | GET `https://www.inberlinwohnen.de/wohnungsfinder/?page=1`; decode HTML `wire:snapshot` attributes, unwrap Livewire array markers, read `data.item` | Municipal-company feed; local filters only; no full-inventory claim |
| `kleinanzeigen` | GET `https://www.kleinanzeigen.de/s-wohnung-mieten/berlin/c203l3331`; parse public `article[data-adid]` cards and optional JSON-LD | Asking-price basis often ambiguous; preserve price without inventing cold/warm rent; local filters |
| `wggesucht` | GET `https://www.wg-gesucht.de/wg-zimmer-in-Berlin.8.0.1.0.html`; public `offer_list_item` / `wgg_card` HTML | Berlin shared-room category, page one; no detail requests; rent remains asking unless explicitly labelled Gesamtmiete (total rent) |
| `wunderflats` | GET `https://wunderflats.com/en/furnished-apartments/berlin`; SSR `article.Listing` cards and Apartment JSON-LD | Furnished temporary rentals, page one; preserve asking price without guessing cold/warm basis |
| `deutschewohnen` | GET `https://www.deutsche-wohnen.com/api/real-estate/search-token`, then GET `https://www.deutsche-wohnen.com/api/deuwo-real-estate/list` with `X-VON-Search-Token`, Accept JSON and Referer | Public short-lived search token, no account authentication or token persistence; Berlin/miete/wohnung/dataSet=deuwo, limit 50, parking flags 0; two guarded requests, first page only, local filters |
| `immoscout` | ImmoScout24 anonymous POST `https://api.mobile.immobilienscout24.de/search/list`, JSON body `{"supportedResultListTypes":[],"userData":{}}`, Accept/Content-Type JSON, app User-Agent `ImmoScout_28.9_27.2_._`; Berlin region geocodes `/de/berlin/berlin`, `realestatetype=apartmentrent`, page 1 | Included by default, no separate opt-in; API may change |

ToS note: ImmoScout24's mobile API use may conflict with its terms; review them before use: https://www.immobilienscout24.de/agb.html

The mobile query maps CLI `--max-warm` to `price=-N` with
`pricetype=calculatedtotalrent`, `--min-rooms` to `numberofrooms=N-`, and sorts
`-firstactivation`; website URLs are not accepted. Local filters apply again to
all normalized records, keeping unknowns for review. No arbitrary URL fetching.

Default HTML User-Agent is transparent: `berlin-apartment-search/0.3.0`.
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
The CSV tracker persists imports across runs without overwriting user status,
verdict or notes, with serialized read-modify-write operations. One-shot watch
keeps durable seen and notification-attempt state separately; see [automation](automation.md).

Deutsche Wohnen live evidence (2026-11-22): the public token→list flow worked;
the corrected live watch returned/kept 50 Berlin offers, unblocked, with ntfy
dry-run only (the API reported 100 total; no second page fetched). The first
watch exposed different field names than the initial fixture; the parser and
synthetic fixture now use observed `wrk_id`, `titel`, `strasse`, `plz`, `ort`,
`preis`, `groesse`, `anzahl_zimmer`, `slug`, `lat`/`lng`. Detail links are the
website's `/mieten/mietangebote/SLUG` route; no detail requests occur. `preis`
stays asking rent: cold/warm basis, costs and dates are unknown. Zero-coordinate
sentinels stay unknown. Unexpected envelopes/cards fail explicitly. Do not bypass
a future 401/403/429. Website: https://www.deutsche-wohnen.com/mieten/mietangebote .

Optional commute services (2026): Nominatim public search JSON at
https://nominatim.openstreetmap.org/search and Transitous planning at
https://api.transitous.org/api/v1/plan. Both pass through the same budgets,
cooldowns, HTTPS-host restriction and no-proxy transport. Geocoding uses an
identifying User-Agent with the project URL, at least a one-second persisted gap
(normally 3–7 seconds), and a 30-day cache. No autocomplete or bulk geocoding.
Policy: https://operations.osmfoundation.org/policies/nominatim/ . Attribute
© OpenStreetMap contributors, ODbL: https://www.openstreetmap.org/copyright .
Transitous receives approximate endpoints only after explicit opt-in; routes
cache for one day per displayed departure bucket. No available route or network
means unknown. Service details: https://transitous.org/ . Verify location, service
and transit accessibility in an official journey planner. Bike requests use
`directModes=BIKE`, empty `transitModes`, and `maxDirectTime` in seconds from the
user's commute limit (default/cap 90 minutes); only direct BIKE/WALK legs count.

Other portals, including Immowelt and Immobilien.de, are not polled. Import saved
pages or exported .eml alerts offline; no tracking redirects, remote assets,
inbox access, cookies or browser automation. Recognized direct links include
Immowelt, the mobile-source portal, Kleinanzeigen, WG-Gesucht, Wunderflats,
HousingAnywhere and Ohne-Makler. JSON-LD can support other portals; unsupported
shapes remain unrecognized. See the [browser recipe](browser-recipe.md). Official portal entry
points (2026): https://www.inberlinwohnen.de/wohnungsfinder/ and
https://www.kleinanzeigen.de/s-wohnung-mieten/berlin/c203l3331

Optional self-notifications use HTTPS POST to `https://ntfy.sh/TOPIC` (plain text)
or `https://api.telegram.org/botTOKEN/sendMessage` (JSON). Only these delivery
paths are allowed by the guard. Secrets come exclusively from environment,
are never printed in receipts, and no portal messages are sent. Dry-run requires
no credentials and sends nothing. Provider docs (2026): https://docs.ntfy.sh/publish/
and https://core.telegram.org/bots/api#sendmessage . Use only your own private
destination; a random ntfy topic is a bearer secret, not an access-control guarantee.
