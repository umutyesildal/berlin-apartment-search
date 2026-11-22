# Privacy

Version 0.1.0 (2026). This skill has no telemetry or hosted backend. Live search
sends a request and optional search filters to each selected portal, exposing
your network address to it. The portal's own policies apply. Local profiles,
results and guard state belong in gitignored ./flat-search/. No data is sent to
an LLM by the Python scripts; an agent client may process text under its own
settings and policies. Review those separately. Gitignore is not encryption.
