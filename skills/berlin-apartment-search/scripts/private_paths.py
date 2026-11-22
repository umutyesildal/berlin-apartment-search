"""Create private output trees without inheriting permissive parent modes."""

import os
from pathlib import Path


def private_directory(directory):
    path = Path(os.path.abspath(directory))
    chain = list(reversed([path] + list(path.parents)))
    root = next((item for item in chain if item.name == 'flat-search'), path)

    def create_parent(parent):
        if not parent.exists():
            create_parent(parent.parent)
            parent.mkdir(mode=0o700, exist_ok=True)
            parent.chmod(0o700)

    create_parent(root.parent)
    for item in chain[chain.index(root):]:
        if item.is_symlink():
            raise OSError('private output directories must not be symbolic links')
        item.mkdir(mode=0o700, exist_ok=True)
        item.chmod(0o700)
    return Path(directory)
