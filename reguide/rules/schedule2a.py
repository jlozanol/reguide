"""Schedule 2A, classification rules for IVD medical devices.

Build this file first. The IVD rule set is far smaller than Schedule 2, which
makes it the right place to prove the whole pipeline end to end.
"""

from ..profile import DeviceProfile
from .engine import RuleHit


def rule_class_4_public_health_risk(profile: DeviceProfile) -> RuleHit | None:
    raise NotImplementedError


ALL_RULES = [
    rule_class_4_public_health_risk,
]
