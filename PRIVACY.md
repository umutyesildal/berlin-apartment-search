# Privacy

Version 0.3.0 (2026). The Python tools have no telemetry or hosted backend. Live search
sends a request and optional search filters to each selected portal, exposing
your network address to it. The portal's own policies apply. Local profiles,
results and guard state belong in gitignored ./flat-search/. No data is sent to
an LLM by the Python scripts; an agent client may process text under its own
settings and policies. Review those separately. Gitignore is not encryption.

Optional geocoding sends a place query to Nominatim; optional routing sends origin
and destination coordinates to Transitous. These requests require explicit CLI
opt-in and are cached locally. Do not disclose private home/work addresses without
consent. Drafts, profile facts, tracker notes and document-date metadata stay local;
the scripts never upload documents or send application messages.

Opted-in self-notifications send a count and a local report path to ntfy or
Telegram. The provider can observe your network address and destination; its
own retention and access policies apply. The local report is not uploaded.
Credentials come only from environment variables. Keep topic URLs, bot tokens
and chat IDs out of profiles, scheduler files, command lines, logs and chat messages.
An unguessable ntfy topic URL alone is not a privacy guarantee.

Exported emails and saved HTML may contain personal data, tracking identifiers
or private links. Imports run offline, skip attachments and remote assets, and
write reports under `flat-search/`. Do not publish raw exports. A watch dry-run
still performs the live search and stores seen state; it only disables delivery.

On POSIX systems, private files are created with mode `0600`, including temporary
files and database files. Private directories use `0700`; existing shared
symlink targets are not chmodded. On Windows, review folder and account ACLs.
These measures are not encryption. Secure your account, backups and shared
folders, and inspect generated files before sharing them.
