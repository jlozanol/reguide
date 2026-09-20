"""Intake. Free text in, a validated DeviceProfile out.

The only model call on the input side. Rules for this module:

- Never invent a field value. Anything not supported by the text stays UNKNOWN.
- Capture the intended purpose verbatim. It is the legally operative statement
  and paraphrasing it changes what the device is.
- Record the supporting phrase in Answer.evidence for every field populated.
"""

from .profile import DeviceProfile


def extract(source_text: str) -> DeviceProfile:
    """First pass over the founder's description."""
    raise NotImplementedError


def next_question(profile: DeviceProfile) -> str | None:
    """The single most useful unresolved field, phrased for a non-regulatory reader.

    Returns None when the relevant branch of the profile is complete.
    """
    raise NotImplementedError


def apply_answer(profile: DeviceProfile, field: str, answer_text: str) -> DeviceProfile:
    """Fold a founder's reply back into the profile with basis ANSWERED."""
    raise NotImplementedError
