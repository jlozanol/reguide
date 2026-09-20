"""Schedule 2, classification rules for general medical devices.

One function per rule. Each takes a DeviceProfile and returns a RuleHit or None.
Keep the function docstring as the clause text so the citation and the code sit
next to each other and drift is visible in review.
"""

from ..profile import DeviceProfile
from .engine import RuleHit


def rule_non_invasive_general(profile: DeviceProfile) -> RuleHit | None:
    raise NotImplementedError


ALL_RULES = [
    rule_non_invasive_general,
]
