# Portable skill and experimental OpenAI bundle

Run these commands from the repository root with Python 3.9+:

```bash
python3 tools/package_skill.py
python3 tools/package_openai.py
```

Outputs are ignored by Git:

- `dist/berlin-apartment-search.zip`: canonical skill instructions, scripts,
  references, assets and MIT license.
- `dist/berlin-apartment-search-openai.zip`: experimental OpenAI-style bundle
  with skill files, plugin metadata and privacy, terms and provenance documents.

Both builders run structural validation first. Neither includes `flat-search/`,
profiles, credentials or a hosted service. Do not add your own data to the skill
directory before packaging. The SVG is an original optional branding asset.

## Using a bundle

Use the canonical archive only with a client that explicitly supports importing
skill files, or extract it for a local agent with a Python runtime. A file upload
alone does not give a chat persistent storage, local scheduling or live network
access through the guard. See the [chat-only prompt](../../docs/chatgpt-prompt.md).

The OpenAI-style archive is a development artifact, not a published or approved
store integration. Client installation, marketplace acceptance and rendering
are not verified. The empty MCP manifest does not start a server. Follow your
client's current import instructions and data policies; do not upload private
records just to install the skill.

The supported baseline is the local repository workflow in the
[README](../../README.md). English documentation is canonical; the product
version is recorded in the skill and plugin manifests.
