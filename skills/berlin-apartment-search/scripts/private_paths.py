"""Create private output trees without inheriting permissive parent modes."""

import os
from pathlib import Path


def private_directory(directory):
    path = Path(os.path.abspath(directory))
    root = Path.cwd().resolve() / 'flat-search'

    def create_parent(parent):
        if not parent.exists():
            create_parent(parent.parent)
            parent.mkdir(mode=0o700, exist_ok=True)
            parent.chmod(0o700)

    if path != root and root not in path.parents:
        create_parent(path)
        return Path(directory)
    chain = [path]
    while chain[-1] != root:
        chain.append(chain[-1].parent)
    for item in reversed(chain):
        if item.is_symlink():
            raise OSError('private output directories must not be symbolic links')
        item.mkdir(mode=0o700, exist_ok=True)
        item.chmod(0o700)
    return Path(directory)
