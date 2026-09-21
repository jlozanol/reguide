"""Flags the report must show beside a verdict, not bury in it.

Shared by the status gate and the classification engine, so both raise the
same kind of thing and the report lays them out one way.
"""

from dataclasses import dataclass
from enum import Enum


class Severity(str, Enum):
    """How loudly the report should raise a flag.

    AMBER: the verdict stands, but a person should look before relying on it.
    RED: the tool could not reach a safe verdict and a person must decide.
    """

    AMBER = "amber"
    RED = "red"


@dataclass(frozen=True)
class Flag:
    """Something the report must show beside the verdict, not bury in it."""

    severity: Severity
    code: str        # stable identifier, for tests and for the report layout
    message: str     # plain words for the founder
    functions: tuple[int, ...] = ()   # indices of the functions it concerns
