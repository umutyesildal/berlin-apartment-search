# OpenAI packaging

`python3 tools/package_openai.py` creates a local bundle in ignored `dist/`.
It contains the canonical scripts and references, no private files or hosted
services. The SVG is an original optional branding asset. Store acceptance,
rendering and installation in an OpenAI client are not verified; P0 guarantees
only offline bundle structure and the canonical repository/skill workflow.
