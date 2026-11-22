"""Build a portable canonical skill archive without any local user data."""

import argparse
import zipfile
from pathlib import Path
from validate_skill import NAME, ROOT, validate


def package(output):
    errors = validate()
    if errors:
        raise ValueError('; '.join(errors))
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as archive:
        for path in sorted((ROOT / 'skills' / NAME).rglob('*')):
            if path.is_file() and '__pycache__' not in path.parts and path.suffix != '.pyc':
                archive.write(path, str(Path(NAME) / path.relative_to(ROOT / 'skills' / NAME)))
        archive.write(ROOT / 'LICENSE', NAME + '/LICENSE')
    return output


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'dist' / (NAME + '.zip'))
    print(package(parser.parse_args().output))
