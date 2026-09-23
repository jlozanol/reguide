"""Intake. Free text in, a validated DeviceProfile out.

The only model call on the input side. Rules for this module:

- Never invent a field value. Anything not supported by the text stays UNKNOWN.
- Capture the intended purpose verbatim. It is the legally operative statement
  and paraphrasing it changes what the device is.
- Record the supporting phrase in Answer.evidence for every field populated.
- Never guess a gate or rule answer. Unsupported means unknown, and unknown
  means ask. Extraction may name a therapeutic purpose limb only with a quoted
  phrase, and never NONE: a "not a device" verdict comes from an answer.

The interview is a loop of three calls:

    profile = extract(text)
    while (question := next_question(profile)) is not None:
        profile = apply_answer(profile, question, choice_ids, reply)

A Question can cover several fields ("which of these apply?"), which is why
next_question returns a Question rather than a field name. Every reply goes
into profile.transcript word for word; that is the evidence for each field it
set, and untraceable_evidence() checks it there.
"""

from typing import Any

from pydantic import BaseModel, Field, model_validator

from .profile import DeviceProfile


class Option(BaseModel):
    """One choice offered to the founder.

    sets maps dotted field names to the value this choice gives them. An
    option marked unsure sets nothing: choosing it records that the founder
    could not answer, so the question is not offered again.
    """

    id: str
    label: str
    sets: dict[str, Any] = Field(default_factory=dict)
    unsure: bool = False

    @model_validator(mode="after")
    def _unsure_sets_nothing(self):
        if self.unsure and self.sets:
            raise ValueError("an unsure option cannot set a value")
        return self


class Question(BaseModel):
    """What next_question hands to the interface.

    text is written for someone who has never read the Regulations. clause
    names the provision the answer feeds, for the report, not for the founder.
    multi is true for a "tick every one that applies" checklist.
    """

    id: str
    text: str
    fields: list[str]
    options: list[Option]
    multi: bool = False
    clause: str = ""

    @model_validator(mode="after")
    def _options_stay_inside_the_question(self):
        """An option may only set fields the question says it covers."""
        covered = set(self.fields)
        for option in self.options:
            stray = set(option.sets) - covered
            if stray:
                raise ValueError(f"option {option.id} sets fields outside the question: {stray}")
        if len({o.id for o in self.options}) != len(self.options):
            raise ValueError("option ids must be unique")
        return self


def extract(source_text: str) -> DeviceProfile:
    """First pass over the founder's description."""
    raise NotImplementedError


def next_question(profile: DeviceProfile) -> Question | None:
    """The most useful unresolved question, phrased for a non-regulatory reader.

    Returns None when nothing askable remains (profile.askable() is empty).
    """
    raise NotImplementedError


def apply_answer(
    profile: DeviceProfile,
    question: Question,
    choice_ids: list[str],
    reply: str | None = None,
) -> DeviceProfile:
    """Fold a founder's reply back into the profile with basis ANSWERED.

    reply is the founder's words, kept verbatim in the transcript. When the
    interface only offers buttons it defaults to the chosen options' labels.
    """
    raise NotImplementedError
