"""Synthetic fixtures and a network-denying base case for all tests."""

import socket
import os
import sys
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / 'skills' / 'berlin-apartment-search' / 'scripts'
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(ROOT / 'tools'))


def fixture(name):
    return (ROOT / 'tests' / 'fixtures' / name).read_text(encoding='utf-8')


@contextmanager
def working_directory(directory):
    previous = Path.cwd()
    os.chdir(directory)
    try:
        yield
    finally:
        os.chdir(previous)


class OfflineTest(unittest.TestCase):
    def setUp(self):
        self.network = patch.object(socket.socket, 'connect', side_effect=AssertionError('network forbidden in tests'))
        self.network.start()
        self.addCleanup(self.network.stop)
