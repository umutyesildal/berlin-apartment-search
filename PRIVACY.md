# Privacy

Version 0.2.0 (2026). This skill has no telemetry or hosted backend. Live search
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
