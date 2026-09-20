"""Draft pack assembly. The second and last model call.

The pack states the classification, the rules that produced it, the funding
triage, the comparable listings and where they disagree, and the questions still
open. Every claim carries its citation. Nothing is asserted that the pipeline
cannot point at a source for.
"""

from .profile import DeviceProfile
from .reimburse import Triage
from .rules import Classification


def build(profile: DeviceProfile, classification: Classification, triage: Triage) -> str:
    """Markdown pack, ready for human review."""
    raise NotImplementedError
