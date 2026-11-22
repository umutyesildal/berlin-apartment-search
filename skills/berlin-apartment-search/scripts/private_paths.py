"""Create private output trees without inheriting permissive parent modes."""

import os
from contextlib import contextmanager
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
    linked = False
    for item in reversed(chain):
        linked = linked or item.is_symlink()
        existed = item.exists()
        item.mkdir(mode=0o700, exist_ok=True)
        if not linked or not existed:
            item.chmod(0o700)
    return Path(directory)


@contextmanager
def private_file(path, mode='w', encoding='utf-8'):
    flags = {'w': os.O_TRUNC, 'a': os.O_APPEND, 'x': os.O_EXCL}
    if mode not in flags:
        raise ValueError('private files support only w, a and x modes')
    path = Path(path)
    private_directory(path.parent)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | flags[mode] | getattr(os, 'O_NOFOLLOW', 0), 0o600)
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, mode, encoding=encoding, closefd=False) as stream:
            yield stream
    finally:
        os.close(descriptor)
