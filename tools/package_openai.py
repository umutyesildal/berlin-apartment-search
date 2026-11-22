"""Build a local OpenAI-style plugin bundle; marketplace acceptance is unverified."""

import argparse
import json
import zipfile
from pathlib import Path
from package_skill import allowed_skill_path, package
from validate_skill import NAME, ROOT


def build(output):
    output = Path(output)
    canonical = package(ROOT / 'dist' / (NAME + '.zip'))
    manifest = json.loads((ROOT / '.codex-plugin/plugin.json').read_text())
    manifest['skills'] = './skills/'
    manifest['interface'] = {'displayName': 'Berlin Apartment Search',
                             'shortDescription': 'Berlin rental search and cost checks',
                             'category': 'Productivity'}
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(canonical) as source, zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as target:
        for name in source.namelist():
            if name.startswith(NAME + '/') and allowed_skill_path(Path(name).relative_to(NAME)):
                target.writestr('skills/' + name, source.read(name))
        target.writestr('.plugin/plugin.json', json.dumps(manifest, indent=2))
        target.writestr('.mcp.json', '{"mcpServers": {}}')
        for name in ('PRIVACY.md', 'TERMS.md', 'NOTICE.md'):
            target.write(ROOT / name, name)
    return output


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'dist' / (NAME + '-openai.zip'))
    print(build(parser.parse_args().output))
