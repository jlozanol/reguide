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

How extraction enforces the rules. The model returns claims, never a profile.
Each claim is checked here before anything is written, and a claim that fails
any check is dropped and reported as a Rejection:

- the target is one intake_fields.EXTRACTABLE allows (never ASK_ONLY);
- the evidence is a phrase of the text. Spacing, curly quotes and dashes are
  normalised for the search, and the text's own characters are what get
  stored, so untraceable_evidence() passes on everything written here;
- the value is one of the field's options, and never UNKNOWN or NONE;
- a "no" is backed by a negation in the evidence (silence is not "no"),
  except for whether a function is software;
- the intended purpose is the evidence itself, word for word, and a product
  name is a phrase inside its evidence;
- the claim is about the right thing: product-level fields on index -1,
  function fields on a function that exists, general.* only on a general
  device function and ivd.* only on an IVD one;
- two claims that give one field different values cancel each other.

Extraction does not prune. A stated fact that the gating does not ask for yet
(a duration before the route is known) is kept, because it may be asked later
and the founder has already answered it. prune() runs before the gate and the
engine, in the end-to-end pipeline.
"""

import re
from dataclasses import dataclass
from enum import Enum, StrEnum
from typing import Any

from pydantic import BaseModel, Field, model_validator

from . import intake_fields as F
from .profile import (
    Answer,
    Basis,
    DeviceKind,
    DeviceProfile,
    FunctionProfile,
    FundingProfile,
    GeneralDeviceProfile,
    IvdProfile,
    TherapeuticPurpose,
    Tri,
)

MAX_FUNCTIONS = 8


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


# --------------------------------------------------------------------------
# Finding a quote in the text
# --------------------------------------------------------------------------

_FOLD = str.maketrans({
    "\u2018": "'", "\u2019": "'", "\u201a": "'", "\u201b": "'",
    "\u201c": '"', "\u201d": '"', "\u201e": '"', "\u201f": '"',
    "\u2013": "-", "\u2014": "-", "\u2212": "-", "\u00a0": " ",
})


def _normalise(text: str) -> tuple[str, list[int]]:
    """Folded text, and for each folded character its index in the original.

    Runs of whitespace fold to one space, so a quote that breaks a line
    differently from the text still matches.
    """
    out: list[str] = []
    index: list[int] = []
    previous_space = False
    for i, char in enumerate(text):
        char = char.translate(_FOLD)
        if char.isspace():
            if previous_space:
                continue
            char = " "
            previous_space = True
        else:
            previous_space = False
        out.append(char)
        index.append(i)
    return "".join(out), index


def locate(evidence: str, source: str) -> str | None:
    """The exact span of source that evidence quotes, or None.

    Tries an exact match, then a folded one (spacing, quotes, dashes), then
    the same ignoring case, then without a trailing full stop or comma the
    text does not have. What comes back is always the source's own
    characters, never the model's.
    """
    evidence = evidence.strip()
    if len(evidence) < 2:
        return None
    if evidence in source:
        return evidence
    folded_source, index = _normalise(source)
    candidates = [evidence]
    trimmed = evidence.rstrip(".,;:")
    if trimmed != evidence:
        candidates.append(trimmed)
    for candidate in candidates:
        folded, _ = _normalise(candidate)
        folded = folded.strip()
        if len(folded) < 2:
            continue
        for haystack, needle in ((folded_source, folded),
                                 (folded_source.lower(), folded.lower())):
            start = haystack.find(needle)
            if start >= 0:
                end = start + len(needle) - 1
                return source[index[start]:index[end] + 1]
    return None


NEGATION = re.compile(
    r"\b(no|not|non|none|nothing|never|without|only|nor|neither|free|cannot)\b"
    r"|n't|\bnon-",
    re.IGNORECASE,
)


# --------------------------------------------------------------------------
# Checking claims
# --------------------------------------------------------------------------

class Reason(StrEnum):
    """Why a claim or a proposed function was dropped."""

    NOT_EXTRACTABLE = "target_not_extractable"
    NO_EVIDENCE = "evidence_not_in_text"
    BAD_VALUE = "value_not_an_option"
    NONE_PURPOSE = "no_therapeutic_purpose_is_never_extracted"
    SILENT_NO = "no_without_a_negation_in_the_evidence"
    NOT_VERBATIM = "value_is_not_the_evidence_word_for_word"
    VALUE_OUTSIDE_EVIDENCE = "value_not_found_inside_the_evidence"
    WRONG_INDEX = "function_index_does_not_fit_the_target"
    WRONG_SECTION = "section_does_not_match_the_function_kind"
    CONFLICT = "claims_disagree_on_this_field"
    TOO_MANY_FUNCTIONS = "more_functions_than_allowed"
    MALFORMED = "malformed_claim"


@dataclass(frozen=True)
class Rejection:
    """A claim or function the checks dropped, kept for the harness and debugging."""

    reason: Reason
    target: str
    function_index: int
    value: str
    evidence: str


@dataclass
class _Claim:
    function_index: int
    target: str
    value: Any
    evidence: str
    raw_value: str


def _reject(out: list[Rejection], reason: Reason, raw: dict[str, Any]) -> None:
    out.append(Rejection(
        reason=reason,
        target=str(raw.get("target", "")),
        function_index=raw.get("function_index", -1)
        if isinstance(raw.get("function_index"), int) else -1,
        value=str(raw.get("value", "")),
        evidence=str(raw.get("evidence", "")),
    ))


def _parse_value(target: str, raw_value: str) -> tuple[Any, Reason | None]:
    kind = F.value_type(target)
    if isinstance(kind, type) and issubclass(kind, Enum):
        try:
            value = kind(raw_value.strip())
        except ValueError:
            return None, Reason.BAD_VALUE
        if value is TherapeuticPurpose.NONE:
            return None, Reason.NONE_PURPOSE
        if getattr(value, "value", None) == "unknown":
            return None, Reason.BAD_VALUE
        return value, None
    text = raw_value.strip()
    return (text, None) if text else (None, Reason.BAD_VALUE)


def _check_claim(raw: Any, source: str, count: int,
                 rejections: list[Rejection]) -> _Claim | None:
    if not isinstance(raw, dict) or not all(
        k in raw for k in ("function_index", "target", "value", "evidence")
    ):
        _reject(rejections, Reason.MALFORMED, raw if isinstance(raw, dict) else {})
        return None
    target, index = raw["target"], raw["function_index"]
    if not isinstance(index, int) or not isinstance(raw["value"], str) \
            or not isinstance(raw["evidence"], str):
        _reject(rejections, Reason.MALFORMED, raw)
        return None
    if target not in F.EXTRACTABLE:
        _reject(rejections, Reason.NOT_EXTRACTABLE, raw)
        return None
    section = F.target_section(target)
    if section in F.PRODUCT_SECTIONS:
        if index != -1:
            _reject(rejections, Reason.WRONG_INDEX, raw)
            return None
    elif not 0 <= index < count:
        _reject(rejections, Reason.WRONG_INDEX, raw)
        return None
    span = locate(raw["evidence"], source)
    if span is None:
        _reject(rejections, Reason.NO_EVIDENCE, raw)
        return None
    value, problem = _parse_value(target, raw["value"])
    if problem is not None:
        _reject(rejections, problem, raw)
        return None
    if target in F.VERBATIM_VALUE:
        if locate(raw["value"], span) != span:
            _reject(rejections, Reason.NOT_VERBATIM, raw)
            return None
        value = span
    if target in F.VALUE_INSIDE_EVIDENCE:
        inside = locate(raw["value"], span)
        if inside is None:
            _reject(rejections, Reason.VALUE_OUTSIDE_EVIDENCE, raw)
            return None
        value = inside
    if value is Tri.NO and target not in F.NEGATION_EXEMPT and not NEGATION.search(span):
        _reject(rejections, Reason.SILENT_NO, raw)
        return None
    return _Claim(index, target, value, span, raw["value"])


def _drop_conflicts(claims: list[_Claim], rejections: list[Rejection]) -> list[_Claim]:
    """One claim per field. Agreeing duplicates keep the first; disagreeing ones all go."""
    groups: dict[tuple[int, str], list[_Claim]] = {}
    for claim in claims:
        groups.setdefault((claim.function_index, claim.target), []).append(claim)
    kept = []
    for group in groups.values():
        if len({repr(c.value) for c in group}) == 1:
            kept.append(group[0])
            continue
        for claim in group:
            rejections.append(Rejection(Reason.CONFLICT, claim.target, claim.function_index,
                                        claim.raw_value, claim.evidence))
    return kept


def _stated(value: Any, evidence: str) -> Answer:
    return Answer(value=value, basis=Basis.STATED, evidence=evidence)


def _build_functions(raw_functions: Any, source: str,
                     rejections: list[Rejection]) -> list[FunctionProfile]:
    functions: list[FunctionProfile] = []
    if not isinstance(raw_functions, list):
        raw_functions = []
    for position, raw in enumerate(raw_functions):
        if position >= MAX_FUNCTIONS:
            _reject(rejections, Reason.TOO_MANY_FUNCTIONS,
                    {"target": "function", "function_index": position})
            continue
        function = FunctionProfile()
        if not isinstance(raw, dict):
            _reject(rejections, Reason.MALFORMED, {"target": "function",
                                                   "function_index": position})
            functions.append(function)
            continue
        name, name_evidence = str(raw.get("name", "")).strip(), str(raw.get("name_evidence", ""))
        name_span = locate(name_evidence, source)
        if name and name_span:
            function.name = _stated(name, name_span)
        elif name:
            _reject(rejections, Reason.NO_EVIDENCE, {"target": "function.name",
                                                     "function_index": position,
                                                     "value": name,
                                                     "evidence": name_evidence})
        description = str(raw.get("description", ""))
        span = locate(description, source)
        if span:
            function.description = _stated(span, span)
        elif description.strip():
            _reject(rejections, Reason.NO_EVIDENCE, {"target": "function.description",
                                                     "function_index": position,
                                                     "value": description,
                                                     "evidence": description})
        functions.append(function)
    return functions or [FunctionProfile()]


def _apply(profile: DeviceProfile, claim: _Claim) -> None:
    section = F.target_section(claim.target)
    name = F.target_field(claim.target)
    answer = _stated(claim.value, claim.evidence)
    if section == "core":
        setattr(profile.core, name, answer)
    elif section == "funding":
        if profile.funding is None:
            profile.funding = FundingProfile()
        setattr(profile.funding, name, answer)
    else:
        function = profile.functions[claim.function_index]
        target = {"function": function, "status": function.status,
                  "general": function.general, "ivd": function.ivd}[section]
        setattr(target, name, answer)


def build_profile(output: dict[str, Any], source_text: str) -> tuple[DeviceProfile,
                                                                     list[Rejection]]:
    """Turn the model's output into a checked profile. No model call here.

    Separate from extract() so that every check can be tested against a
    hand-written output, including outputs a strict schema would never let
    the live model produce.
    """
    rejections: list[Rejection] = []
    if not isinstance(output, dict):
        output = {}
    functions = _build_functions(output.get("functions"), source_text, rejections)
    profile = DeviceProfile(source_text=source_text, functions=functions)

    raw_claims = output.get("claims")
    checked = [
        claim for raw in (raw_claims if isinstance(raw_claims, list) else [])
        if (claim := _check_claim(raw, source_text, len(functions), rejections)) is not None
    ]
    claims = _drop_conflicts(checked, rejections)

    # Kind first: it decides which section a function's other claims can land in.
    for claim in claims:
        if claim.target == "function.kind":
            _apply(profile, claim)
    for function in profile.functions:
        kind = function.branch()
        if kind is DeviceKind.GENERAL:
            function.general = GeneralDeviceProfile()
        elif kind is DeviceKind.IVD:
            function.ivd = IvdProfile()

    for claim in claims:
        if claim.target == "function.kind":
            continue
        section = F.target_section(claim.target)
        if section in ("general", "ivd"):
            function = profile.functions[claim.function_index]
            if getattr(function, section) is None:
                rejections.append(Rejection(Reason.WRONG_SECTION, claim.target,
                                            claim.function_index, claim.raw_value,
                                            claim.evidence))
                continue
        _apply(profile, claim)
    return profile, rejections


def extract_with_report(source_text: str, client: Any = None) -> tuple[DeviceProfile,
                                                                       list[Rejection]]:
    """extract(), plus every claim the checks dropped and why."""
    if client is None:
        from .llm import OpenAIIntake

        client = OpenAIIntake()
    return build_profile(client.complete(source_text), source_text)


def extract(source_text: str, client: Any = None) -> DeviceProfile:
    """First pass over the founder's description.

    client defaults to the live OpenAI call. Tests pass a CassetteClient or a
    fake; nothing in the test suite reaches the network.
    """
    return extract_with_report(source_text, client)[0]


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
