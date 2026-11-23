"""Build a portable canonical skill archive without any local user data."""

import argparse
import zipfile
from pathlib import Path
from validate_skill import NAME, ROOT, validate


def allowed_skill_path(path):
    path = Path(path)
    if any(part in ('flat-search', '__pycache__', '..') or part.startswith('.env') for part in path.parts):
        return False
    if path.as_posix() in ('SKILL.md', 'LICENSE'):
        return True
    extensions = {'scripts': {'.py'}, 'references': {'.md'}, 'assets': {'.txt', '.json', '.yml', '.yaml'}}
    return len(path.parts) > 1 and path.suffix in extensions.get(path.parts[0], set())


def package(output):
    errors = validate()
    if errors:
        raise ValueError('; '.join(errors))
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as archive:
        skill = ROOT / 'skills' / NAME
        for path in sorted(skill.rglob('*')):
            relative = path.relative_to(skill)
            if path.is_file() and not path.is_symlink() and allowed_skill_path(relative):
                if skill.resolve() in path.resolve().parents:
                    archive.write(path, str(Path(NAME) / relative))
        archive.write(ROOT / 'LICENSE', NAME + '/LICENSE')
    return output


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'dist' / (NAME + '.zip'))
    print(package(parser.parse_args().output))
