# Contributing

Follow [AGENTS.md](AGENTS.md). Add synthetic fixtures for every parser change;
never add live scraped personal data. Do not run networking in unit tests.
Keep changes within P0 unless a later phase is explicitly requested.

Run both checks in the README before committing. Live probes are optional manual
checks, one request per source, governed by the same persisted request budget.
