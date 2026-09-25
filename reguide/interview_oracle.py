"""Run the interview against a fixture, answering as the fixture would.

The oracle is a founder who knows every answer the fixture records and
nothing else: for each question it picks the option that sets the fixture's
value, and says "not sure" when the fixture has no value. It measures two
things:

- how many screens the interview takes for a product (the step 4 targets
  are under 20 for a typical product and under 35 for the most complex);
- whether the answers it gathered are enough: the finished profile is
  scored like the fixture itself, so an ordering or an early stop that skips
  a question the engine needs shows up as a failure, not as a short count.
  Once the class is settled the interview stops, so the fixture's rule may
  be one left unasked at the same class; that still agrees (see
  scoring.score_fixture, unasked_rule_ok).

It starts either from nothing but the right number of functions (blank), or
from a recorded extraction of one of the fixture's intake texts (extracted),
which is closer to a real interview. No model call either way.

Answers are written the way apply_answer will write them (step 5): basis
ANSWERED, a Turn holding the chosen option's label as the reply, and that
reply as the evidence. A kind answer opens its section. settle() runs after
every answer.
"""

import json
from dataclasses import dataclass, field
from pathlib import Path

from .extract import Question, build_profile
from .intake_scoring import CASSETTE_DIR, Cassette, IntakeCase, cassette_state, load_cases
from .interview import next_question, settle
from .profile import (
    Answer,
    Basis,
    DeviceKind,
    DeviceProfile,
    FunctionProfile,
    GeneralDeviceProfile,
    IvdProfile,
    Tri,
    Turn,
)
from .questions import CHECKLIST_NONE, CHECKLIST_PARTIAL, checklist_reply
from .scoring import AGREE, FIXTURE_DIR, score_fixture

MAX_QUESTIONS = 400


@dataclass
class OracleRun:
    slug: str
    start: str                        # "blank" or the intake case name
    questions: int = 0
    unsure: list[str] = field(default_factory=list)
    asked: list[str] = field(default_factory=list)
    checklists: list[str] = field(default_factory=list)
    profile: DeviceProfile | None = None
    verdicts: list[str] = field(default_factory=list)

    @property
    def agrees(self) -> bool:
        return bool(self.verdicts) and all(v == AGREE for v in self.verdicts)


def blank(full: DeviceProfile) -> DeviceProfile:
    """The fixture's number of functions, and nothing else."""
    return DeviceProfile(functions=[FunctionProfile() for _ in full.functions])


def extracted(case: IntakeCase, cassettes: Path = CASSETTE_DIR) -> DeviceProfile | None:
    """The profile a recorded extraction gives for this intake case, or None."""
    state, output = cassette_state(case, cassettes)
    if state is not Cassette.OK:
        return None
    return build_profile(output, case.text)[0]


def _set(profile: DeviceProfile, dotted: str, answer: Answer) -> None:
    parts = dotted.split(".")
    node = profile
    for part in parts[:-1]:
        node = node[int(part)] if part.isdigit() else getattr(node, part)
    setattr(node, parts[-1], answer)


def _open_section(profile: DeviceProfile, dotted: str) -> None:
    parts = dotted.split(".")
    if len(parts) != 3 or parts[2] != "kind":
        return
    function = profile.functions[int(parts[1])]
    kind = function.branch()
    if kind is DeviceKind.GENERAL and function.general is None:
        function.general = GeneralDeviceProfile()
    elif kind is DeviceKind.IVD and function.ivd is None:
        function.ivd = IvdProfile()


def _answer_checklist(run: OracleRun, profile: DeviceProfile, full: DeviceProfile,
                      question: Question) -> None:
    """Tick what the fixture says yes to, as apply_answer will read it.

    With every item known: tick the yes items (or "None of these apply"),
    and every unticked item becomes no. With any item unknown: tick the yes
    items and "I'm not sure about some of these", which leaves the rest open.
    """
    run.asked.append(question.id)
    run.checklists.append(question.id)
    items = {o.id: o for o in question.options
             if o.id not in (CHECKLIST_NONE, CHECKLIST_PARTIAL)}
    wanted = {}
    for option in items.values():
        [(dotted, _)] = option.sets.items()
        answer = full.answer_at(dotted)
        wanted[option.id] = answer.value if answer is not None and answer.resolved else None
    ticked = [i for i, v in wanted.items() if v is Tri.YES]
    partial = any(v is None for v in wanted.values())
    if partial:
        chosen = ticked + [CHECKLIST_PARTIAL]
    else:
        chosen = ticked or [CHECKLIST_NONE]
    reply = checklist_reply(question, chosen)
    answered = []
    for option_id, option in items.items():
        [(dotted, _)] = option.sets.items()
        if option_id in ticked:
            value = Tri.YES
        elif partial:
            continue
        else:
            value = Tri.NO
        _set(profile, dotted, Answer(value=value, basis=Basis.ANSWERED, evidence=option.label))
        answered.append(dotted)
    # The turn covers the fields it answered. Items left open are not marked
    # unsure: they come back as single questions.
    profile.transcript.append(Turn(question_id=question.id, fields=answered,
                                   asked=question.text, reply=reply))


def interview(slug: str, data: dict, start: DeviceProfile, label: str = "blank") -> OracleRun:
    """Answer every question the interview asks, from the fixture."""
    full = DeviceProfile.model_validate(data["profile"])
    profile = settle(start)
    run = OracleRun(slug=slug, start=label)
    while (question := next_question(profile)) is not None:
        if run.questions >= MAX_QUESTIONS:
            raise RuntimeError(f"{slug}: more than {MAX_QUESTIONS} questions")
        run.questions += 1
        if question.multi:
            _answer_checklist(run, profile, full, question)
            settle(profile)
            continue
        dotted = question.fields[0]
        run.asked.append(dotted)
        want = full.answer_at(dotted)
        if want is None or not want.resolved or want.value is None:
            run.unsure.append(dotted)
            profile.transcript.append(Turn(question_id=question.id, fields=[dotted],
                                           asked=question.text, reply="Not sure",
                                           unsure=True))
            continue
        chosen = next((o for o in question.options
                       if not o.unsure and o.sets.get(dotted) == want.value), None)
        reply = chosen.label if chosen is not None else str(getattr(want.value, "value",
                                                                     want.value))
        profile.transcript.append(Turn(question_id=question.id, fields=[dotted],
                                       asked=question.text, reply=reply))
        _set(profile, dotted, Answer(value=want.value, basis=Basis.ANSWERED, evidence=reply))
        _open_section(profile, dotted)
        settle(profile)

    run.profile = profile
    scored = dict(data, profile=profile.model_dump(mode="json"))
    run.verdicts = [row.verdict for row in score_fixture(slug, scored, unasked_rule_ok=True)]
    return run


def fixtures(directory: Path = FIXTURE_DIR) -> list[tuple[str, dict]]:
    return [(p.stem, json.loads(p.read_text())) for p in sorted(directory.glob("*.json"))]


def run_blank(directory: Path = FIXTURE_DIR) -> list[OracleRun]:
    runs = []
    for slug, data in fixtures(directory):
        full = DeviceProfile.model_validate(data["profile"])
        runs.append(interview(slug, data, blank(full)))
    return runs


def run_extracted(directory: Path = FIXTURE_DIR,
                  cassettes: Path = CASSETTE_DIR) -> list[OracleRun]:
    runs = []
    data = dict(fixtures(directory))
    for case in load_cases(directory):
        start = extracted(case, cassettes)
        if start is None:
            continue
        runs.append(interview(case.slug, data[case.slug], start, case.name))
    return runs
