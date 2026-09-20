"""Reimbursement triage. Runs after classification, never beside it.

Answers three questions and nothing more:
  1. Which funding channel applies: MBS service, Prescribed List, or hospital budget.
  2. Which Prescribed List tier the class and novelty imply.
  3. Whether a related MBS item already exists, or has to be created first.

This is triage, not health technology assessment. It narrows the question and
names the sequencing trap. It does not model evidence requirements.
"""

from dataclasses import dataclass

from .profile import DeviceProfile
from .rules import Classification


@dataclass
class Triage:
    channel: str
    tier: str | None
    mbs_item_exists: bool | None
    sequencing_note: str
    caveats: list[str]


def triage(profile: DeviceProfile, classification: Classification) -> Triage:
    raise NotImplementedError
