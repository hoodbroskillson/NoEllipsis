import os
import sys
from pathlib import Path


def alpha():
    return os.name


def beta():
    return sys.version


class Service:
    def start(self):
        return Path(".")

    def stop(self):
        return "ok"
