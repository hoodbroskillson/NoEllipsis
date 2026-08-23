"""Legitimate constructs that must not be flagged."""

from abc import ABC, abstractmethod
from typing import Protocol


def show():
    print("...")


def narrative():
    return "Wait... what happened?"


def docs():
    return "See https://example.com/a...z for details."


class Worker(ABC):
    @abstractmethod
    def run(self):
        pass


class Closable(Protocol):
    def close(self) -> None: ...


class Box:
    def __init__(self) -> None:
        pass
