"""Offline structural validation for the canonical skill and agent manifests."""

import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
NAME = 'berlin-apartment-search'
SKILL = ROOT / 'skills' / NAME
REFERENCES = ('rental-law', 'mietspiegel', 'wbs', 'landeseigene', 'scams',
              'application-dossier', 'districts', 'after-signing', 'newcomers', 'sources',
              'automation', 'browser-recipe')
MANIFESTS = ('.claude-plugin/plugin.json', '.claude-plugin/marketplace.json',
             '.codex-plugin/plugin.json', '.agents/plugins/marketplace.json')


def validate(root=ROOT):
    errors = []
    skill = root / 'skills' / NAME
    path = skill / 'SKILL.md'
    if not path.is_file():
        return ['canonical SKILL.md missing']
    text = path.read_text(encoding='utf-8')
    front = re.match(r'\A---\n(.*?)\n---\n', text, re.S)
    if not front:
        errors.append('missing or unclosed YAML frontmatter')
    header = front.group(1) if front else ''
    if not re.search(r'^name: ' + NAME + r'$', header, re.M):
        errors.append('frontmatter name mismatch')
    description = re.search(r'^description: (.+)$', header, re.M)
    if not description or len(description.group(1)) > 1024:
        errors.append('description missing or too long')
    version = re.search(r'^  version: [\"\x27]?([\d.]+)', header, re.M)
    version = version.group(1) if version else None
    if not version:
        errors.append('metadata.version missing')
    if len(text.splitlines()) > 500:
        errors.append('SKILL.md exceeds 500 lines')
    for relative in set(re.findall(r'(?:references|scripts|assets)/[\w./-]+\.[\w]+', text)):
        if not (skill / relative).is_file():
            errors.append('missing skill resource: ' + relative)
    for name in REFERENCES:
        reference = skill / 'references' / (name + '.md')
        if not reference.is_file():
            errors.append('missing reference: ' + name)
        else:
            body = reference.read_text(encoding='utf-8')
            if 'Data-as-of:' not in body or 'https://' not in body or 'not legal advice' not in body:
                errors.append('reference missing date/source/disclaimer: ' + name)
    for relative in MANIFESTS:
        try:
            manifest = json.loads((root / relative).read_text(encoding='utf-8'))
            if manifest.get('name') != NAME:
                errors.append('manifest name mismatch: ' + relative)
            versions = [manifest['version']] if 'version' in manifest else []
            versions += [entry.get('version') for entry in manifest.get('plugins', [])]
            if not versions or any(value != version for value in versions):
                errors.append('manifest version mismatch: ' + relative)
            for key in ('skills', 'commands'):
                for target in manifest.get(key, []):
                    if not (root / target).exists():
                        errors.append('manifest target missing: ' + target)
        except (OSError, ValueError, TypeError) as error:
            errors.append(relative + ': ' + str(error))
    try:
        mcp = json.loads((root / '.mcp.json').read_text(encoding='utf-8'))
        if mcp != {'mcpServers': {}}:
            errors.append('P0 must not depend on hosted MCP servers')
    except (OSError, ValueError) as error:
        errors.append('invalid MCP manifest: ' + str(error))
    for directory in ('.agents', '.claude'):
        link = root / directory / 'skills' / NAME
        if not link.is_symlink() or link.resolve() != skill.resolve():
            errors.append('skill symlink missing or incorrect: ' + directory)
    if 'flat-search/' not in (root / '.gitignore').read_text().splitlines():
        errors.append('private data directory is not gitignored')
    for name in ('README.md', 'README.de.md'):
        readme = root / name
        if not readme.is_file():
            errors.append('missing ' + name)
            continue
        body = readme.read_text(encoding='utf-8')
        for link in re.findall(r'\]\(([^)]+)\)', body):
            if not re.match(r'[a-z]+://|#', link) and not (root / link.split('#')[0]).exists():
                errors.append('broken README link: ' + link)
        if re.search(r'immoscout|immobilienscout', body, re.I):
            errors.append('source branding belongs only in sources reference')
    for directory in (skill, root / 'tests', root / 'tools'):
        for path in directory.rglob('*'):
            if path.suffix in ('.py', '.md', '.yml', '.json', '.html') and path.is_file():
                body = path.read_text(encoding='utf-8')
                if re.search(r'/(?:home|Users)/[^\s/]+/', body):
                    errors.append('machine-specific path: ' + str(path.relative_to(root)))
    return errors


def main():
    errors = validate()
    if errors:
        for error in errors:
            print('FAIL: ' + error)
        return 1
    print('PASS: berlin-apartment-search skill, %d references, manifests, symlinks and README links' % len(REFERENCES))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
