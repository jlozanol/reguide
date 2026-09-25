"""Schedule 2A, classification rules for IVD medical devices.

One function per rule. Each takes the function's IvdProfile and returns a
RuleHit, a Pending or None. The docstring holds the clause text verbatim from
Compilation 72, below a first line naming the clause, so the citation and the
code sit next to each other and drift is visible in review.
tests/test_schedule2a.py checks every docstring against the clause files.

Clauses 1.1 to 1.4 are one rule per paragraph, because a device can meet
several and each hit cites its own. Their fields sit behind three gates
(profile.py): a paragraph behind a gate answered no is silent without
asking, and a gate left unanswered blocks the paragraphs behind it.
Regulation 3.3(7) then takes the highest class among the paragraphs that
fire.

Clauses 1.5, 1.6(2) and 1.8 each open "Despite clauses ...", so each
displaces the clauses it names even though it gives a lower class (see
engine.py).

The fallback is written. Clause 1.6(1) is read narrowly, as the
international model the rules came from reads it (IMDRF/GHTF rule 5): an
ancillary reagent or article used in a specific examination, such as a
buffer, a wash solution or a general reagent, not the test itself. Read
literally it would catch almost every test kit and leave 1.7 nearly empty.
1.6(1) has no "despite", so any other clause that applies outranks it.
Clause 1.7 applies to a device "not mentioned in this Schedule": it fires
only when no other clause hits and nothing is left unanswered. Either way an
amber flag asks a person to confirm the reading.

Classes are reported as "Class N IVD". Clauses 1.1 to 1.3 and 1.5 to 1.7 also
name the in-house equivalent; 1.4 and 1.8 do not. The profile has no
in-house field yet.
"""

from dataclasses import replace

from ..flags import Flag, Severity
from ..profile import IVD_ORDER, IvdProfile, Tri
from .engine import (
    REGULATIONS,
    Classification,
    Pending,
    RuleHit,
    apply_ceilings,
    clauses,
    known,
    resolve,
)

PREFIX = "s2a"


def cite(reference: str) -> str:
    return f"{REGULATIONS} Schedule 2A clause {reference}"


def _because(ivd: IvdProfile, *names: str) -> str:
    parts = []
    for name in names:
        answer = getattr(ivd, name)
        parts.append(f'{name} is {answer.value.value} ({answer.basis.value}: "{answer.evidence}")'
                     if answer.evidence else f"{name} is {answer.value.value} "
                     f"({answer.basis.value})")
    return "; ".join(parts)


def _lookup(ivd: IvdProfile, name: str, rule_id: str, reference: str) -> Tri | Pending:
    value = known(getattr(ivd, name))
    if value is None:
        return Pending(rule_id, cite(reference), f"{name} is unresolved", (f"ivd.{name}",))
    return value


# --------------------------------------------------------------------------
# Clauses 1.1 to 1.4, one rule per paragraph
# --------------------------------------------------------------------------

AGENT = "detects_infectious_agent"
TYPING = "types_blood_or_tissue"


def _paragraph(ivd: IvdProfile, field: str, reference: str, result: str,
               gate: str | None = None):
    """A paragraph that applies when its field is yes, behind an optional gate."""
    rule_id = f"{PREFIX}-{reference}"
    if gate is not None:
        opened = _lookup(ivd, gate, rule_id, reference)
        if opened is not Tri.YES:
            return opened if isinstance(opened, Pending) else None
    value = _lookup(ivd, field, rule_id, reference)
    if value is not Tri.YES:
        return value if isinstance(value, Pending) else None
    names = (gate, field) if gate else (field,)
    return RuleHit(rule_id, cite(reference), result, _because(ivd, *names))


def rule_1_1_a(ivd: IvdProfile):
    """Schedule 2A clause 1.1(a).

    An IVD medical device intended to be used for any of the following
    purposes is classified as a Class 4 IVD medical device or a Class 4
    in-house IVD medical device:

    (a) to detect the presence of, or exposure to, transmissible agents in
    blood, blood components, blood products, cells, tissues or organs or any
    derivatives of these products of human or animal origin, in order to
    assess their suitability for transfusion or transplantation;
    """
    return _paragraph(ivd, "screens_donations_for_transmissible_agents", "1.1(a)",
                      "Class 4 IVD", AGENT)


def rule_1_1_b(ivd: IvdProfile):
    """Schedule 2A clause 1.1(b).

    An IVD medical device intended to be used for any of the following
    purposes is classified as a Class 4 IVD medical device or a Class 4
    in-house IVD medical device:

    (b) to detect the presence of, or exposure to, a transmissible agent that
    causes a serious disease with a high risk of propagation in Australia.
    """
    return _paragraph(ivd, "agent_serious_with_high_propagation_risk", "1.1(b)",
                      "Class 4 IVD", AGENT)


def rule_1_2_1(ivd: IvdProfile):
    """Schedule 2A clause 1.2(1).

    (1) An IVD medical device is classified as a Class 3 IVD medical device or
    a Class 3 in-house IVD medical device if:

    (a) the device is intended to be used for detection of biological markers
    in order to assess the immunological compatibility of blood, blood
    components, blood products, cells, tissues or organs that are intended for
    transfusion or transplantation; and

    (b) the device is not a device mentioned in subclause (2).
    """
    hit = _paragraph(ivd, "assesses_transfusion_or_transplant_compatibility", "1.2(1)",
                     "Class 3 IVD", TYPING)
    if not isinstance(hit, RuleHit):
        return hit
    listed = _lookup(ivd, "detects_listed_blood_group_marker", hit.rule_id, "1.2(1)")
    if listed is not Tri.NO:
        # A listed marker is 1.2(2), Class 4, and paragraph (b) excludes it here.
        return listed if isinstance(listed, Pending) else None
    return replace(hit, because=_because(
        ivd, TYPING, "assesses_transfusion_or_transplant_compatibility",
        "detects_listed_blood_group_marker"))


def rule_1_2_2(ivd: IvdProfile):
    """Schedule 2A clause 1.2(2).

    (2) An IVD medical device intended to detect any of the following markers
    mentioned for the following blood group systems is classified as a Class 4
    IVD medical device or a Class 4 in-house IVD medical device:
    """
    # The markers are listed in paragraphs (a) to (e) of the clause: ABO,
    # Rhesus, Kell, Kidd and Duffy systems. One question covers the list.
    return _paragraph(ivd, "detects_listed_blood_group_marker", "1.2(2)",
                      "Class 4 IVD", TYPING)


CLASS_3 = "Class 3 IVD"


def rule_1_3_a(ivd: IvdProfile):
    """Schedule 2A clause 1.3(a).

    An IVD medical device is classified as a Class 3 IVD medical device or a
    Class 3 in-house IVD medical device if it is intended for any of the
    following uses:

    (a) detecting the presence of, or exposure to, a sexually transmitted
    agent;
    """
    return _paragraph(ivd, "detects_sexually_transmitted_agent", "1.3(a)", CLASS_3, AGENT)


def rule_1_3_b(ivd: IvdProfile):
    """Schedule 2A clause 1.3(b).

    An IVD medical device is classified as a Class 3 IVD medical device or a
    Class 3 in-house IVD medical device if it is intended for any of the
    following uses:

    (b) detecting the presence in cerebrospinal fluid or blood of an infectious
    agent with a risk of limited propagation;
    """
    return _paragraph(ivd, "detects_limited_propagation_agent_in_csf_or_blood", "1.3(b)",
                      CLASS_3, AGENT)


def rule_1_3_c(ivd: IvdProfile):
    """Schedule 2A clause 1.3(c).

    An IVD medical device is classified as a Class 3 IVD medical device or a
    Class 3 in-house IVD medical device if it is intended for any of the
    following uses:

    (c) detecting the presence of an infectious agent, if there is a
    significant risk that an erroneous result would cause death or severe
    disability to the individual or foetus being tested;
    """
    return _paragraph(ivd, "error_could_cause_death_or_severe_disability", "1.3(c)",
                      CLASS_3, AGENT)


def rule_1_3_d(ivd: IvdProfile):
    """Schedule 2A clause 1.3(d).

    An IVD medical device is classified as a Class 3 IVD medical device or a
    Class 3 in-house IVD medical device if it is intended for any of the
    following uses:

    (d) pre-natal screening of women in order to determine their immune status
    towards transmissible agents;
    """
    return _paragraph(ivd, "prenatal_immune_status_screening", "1.3(d)", CLASS_3, AGENT)


def rule_1_3_e(ivd: IvdProfile):
    """Schedule 2A clause 1.3(e).

    An IVD medical device is classified as a Class 3 IVD medical device or a
    Class 3 in-house IVD medical device if it is intended for any of the
    following uses:

    (e) determining infective disease status or immune status, if there is a
    risk that an erroneous result will lead to a patient management decision
    resulting in an imminent life-threatening situation for the patient;
    """
    return _paragraph(ivd, "infective_status_error_life_threatening", "1.3(e)",
                      CLASS_3, AGENT)


def rule_1_3_f_i(ivd: IvdProfile):
    """Schedule 2A clause 1.3(f)(i).

    An IVD medical device is classified as a Class 3 IVD medical device or a
    Class 3 in-house IVD medical device if it is intended for any of the
    following uses:

    (f) the selection of patients:

    (i) for selective therapy and management; or
    """
    return _paragraph(ivd, "selects_patients_for_therapy", "1.3(f)(i)", CLASS_3)


def rule_1_3_f_ii(ivd: IvdProfile):
    """Schedule 2A clause 1.3(f)(ii).

    An IVD medical device is classified as a Class 3 IVD medical device or a
    Class 3 in-house IVD medical device if it is intended for any of the
    following uses:

    (f) the selection of patients:

    (ii) for disease staging; or
    """
    return _paragraph(ivd, "selects_patients_for_disease_staging", "1.3(f)(ii)", CLASS_3)


def rule_1_3_f_iii(ivd: IvdProfile):
    """Schedule 2A clause 1.3(f)(iii).

    An IVD medical device is classified as a Class 3 IVD medical device or a
    Class 3 in-house IVD medical device if it is intended for any of the
    following uses:

    (f) the selection of patients:

    (iii) in the diagnosis of cancer;
    """
    return _paragraph(ivd, "selects_patients_in_cancer_diagnosis", "1.3(f)(iii)", CLASS_3)


def rule_1_3_fa(ivd: IvdProfile):
    """Schedule 2A clause 1.3(fa).

    An IVD medical device is classified as a Class 3 IVD medical device or a
    Class 3 in-house IVD medical device if it is intended for any of the
    following uses:

    (fa) use as an IVD companion diagnostic;
    """
    return _paragraph(ivd, "is_companion_diagnostic", "1.3(fa)", CLASS_3)


def rule_1_3_g(ivd: IvdProfile):
    """Schedule 2A clause 1.3(g).

    An IVD medical device is classified as a Class 3 IVD medical device or a
    Class 3 in-house IVD medical device if it is intended for any of the
    following uses:

    (g) human genetic testing;
    """
    return _paragraph(ivd, "is_human_genetic_test", "1.3(g)", CLASS_3)


def rule_1_3_h(ivd: IvdProfile):
    """Schedule 2A clause 1.3(h).

    An IVD medical device is classified as a Class 3 IVD medical device or a
    Class 3 in-house IVD medical device if it is intended for any of the
    following uses:

    (h) to monitor levels of medicines, substances or biological components,
    when there is a risk that an erroneous result will lead to a patient
    management decision resulting in an immediate life-threatening situation
    for the patient;
    """
    return _paragraph(ivd, "monitors_levels_error_life_threatening", "1.3(h)", CLASS_3)


def rule_1_3_i(ivd: IvdProfile):
    """Schedule 2A clause 1.3(i).

    An IVD medical device is classified as a Class 3 IVD medical device or a
    Class 3 in-house IVD medical device if it is intended for any of the
    following uses:

    (i) the management of patients suffering from a life-threatening
    infectious disease;
    """
    return _paragraph(ivd, "manages_life_threatening_infectious_disease", "1.3(i)",
                      CLASS_3, AGENT)


def rule_1_3_j(ivd: IvdProfile):
    """Schedule 2A clause 1.3(j).

    An IVD medical device is classified as a Class 3 IVD medical device or a
    Class 3 in-house IVD medical device if it is intended for any of the
    following uses:

    (j) screening for congenital disorders in a foetus.
    """
    return _paragraph(ivd, "screens_foetus_for_congenital_disorders", "1.3(j)", CLASS_3)


def rule_1_4(ivd: IvdProfile):
    """Schedule 2A clause 1.4.

    An IVD medical device for self-testing is classified as a Class 3 IVD
    medical device unless:

    (a) the result of the examination is not determining a serious condition,
    ailment or defect; or

    (b) the examination is preliminary and follow-up additional testing is
    required.
    """
    rule_id = f"{PREFIX}-1.4"
    self_test = _lookup(ivd, "is_self_test", rule_id, "1.4")
    if self_test is not Tri.YES:
        return self_test if isinstance(self_test, Pending) else None
    exceptions = ["result_not_determining_serious_condition",
                  "preliminary_with_follow_up_testing"]
    answers = [_lookup(ivd, name, rule_id, "1.4") for name in exceptions]
    if Tri.YES in answers:
        return None             # an exception applies; another clause decides
    for answer in answers:
        if isinstance(answer, Pending):
            return answer
    return RuleHit(rule_id, cite("1.4"), CLASS_3,
                   _because(ivd, "is_self_test", *exceptions))


# --------------------------------------------------------------------------
# Lookups
# --------------------------------------------------------------------------


def rule_1_5(ivd: IvdProfile):
    """Schedule 2A clause 1.5.

    Despite clauses 1.1 to 1.4, an IVD medical device that is intended to be
    used as non assay-specific quality control material is classified as a
    Class 2 IVD medical device or a Class 2 in-house IVD medical device.
    """
    rule_id = f"{PREFIX}-1.5"
    value = _lookup(ivd, "is_quality_control_material", rule_id, "1.5")
    if value is not Tri.YES:
        return value if isinstance(value, Pending) else None
    return RuleHit(
        rule_id=rule_id,
        citation=cite("1.5"),
        result="Class 2 IVD",
        because=_because(ivd, "is_quality_control_material"),
        displaces=clauses(PREFIX, "1.1", "1.2", "1.3", "1.4"),
    )


DESPITE_1_6_2 = clauses(PREFIX, "1.1", "1.2", "1.3", "1.4", "1.5")


def rule_1_6_2_a(ivd: IvdProfile):
    """Schedule 2A clause 1.6(2)(a).

    (2) Despite clauses 1.1 to 1.5, the following IVD medical devices are
    classified as Class 1 IVD medical devices or Class 1 in-house IVD medical
    devices:

    (a) an instrument, intended by the manufacturer, to be specifically used
    for in vitro diagnostic procedures;
    """
    rule_id = f"{PREFIX}-1.6(2)(a)"
    value = _lookup(ivd, "is_ivd_instrument", rule_id, "1.6(2)(a)")
    if value is not Tri.YES:
        return value if isinstance(value, Pending) else None
    return RuleHit(rule_id, cite("1.6(2)(a)"), "Class 1 IVD",
                   _because(ivd, "is_ivd_instrument"), DESPITE_1_6_2)


def rule_1_6_2_b(ivd: IvdProfile):
    """Schedule 2A clause 1.6(2)(b).

    (2) Despite clauses 1.1 to 1.5, the following IVD medical devices are
    classified as Class 1 IVD medical devices or Class 1 in-house IVD medical
    devices:

    (b) a specimen receptacle, other than a specimen receptacle that is
    intended for use in self-testing;
    """
    rule_id = f"{PREFIX}-1.6(2)(b)"
    value = _lookup(ivd, "is_specimen_receptacle", rule_id, "1.6(2)(b)")
    if value is not Tri.YES:
        return value if isinstance(value, Pending) else None
    self_test = _lookup(ivd, "is_self_test", rule_id, "1.6(2)(b)")
    if self_test is not Tri.NO:
        # A self-test receptacle is outside (b) and falls to the other rules.
        return self_test if isinstance(self_test, Pending) else None
    return RuleHit(rule_id, cite("1.6(2)(b)"), "Class 1 IVD",
                   _because(ivd, "is_specimen_receptacle", "is_self_test"), DESPITE_1_6_2)


def rule_1_6_2_c(ivd: IvdProfile):
    """Schedule 2A clause 1.6(2)(c).

    (2) Despite clauses 1.1 to 1.5, the following IVD medical devices are
    classified as Class 1 IVD medical devices or Class 1 in-house IVD medical
    devices:

    (c) a microbiological culture medium.
    """
    rule_id = f"{PREFIX}-1.6(2)(c)"
    value = _lookup(ivd, "is_culture_medium", rule_id, "1.6(2)(c)")
    if value is not Tri.YES:
        return value if isinstance(value, Pending) else None
    return RuleHit(rule_id, cite("1.6(2)(c)"), "Class 1 IVD",
                   _because(ivd, "is_culture_medium"), DESPITE_1_6_2)


def rule_1_8(ivd: IvdProfile):
    """Schedule 2A clause 1.8.

    Despite clauses 1.1 to 1.7, an IVD medical device is classified as a
    Class 1 IVD medical device if it is intended by the manufacturer for
    export only.
    """
    rule_id = f"{PREFIX}-1.8"
    value = _lookup(ivd, "is_export_only", rule_id, "1.8")
    if value is not Tri.YES:
        return value if isinstance(value, Pending) else None
    return RuleHit(rule_id, cite("1.8"), "Class 1 IVD", _because(ivd, "is_export_only"),
                   clauses(PREFIX, "1.1", "1.2", "1.3", "1.4", "1.5", "1.6", "1.7"))


# --------------------------------------------------------------------------
# Evaluation
# --------------------------------------------------------------------------

def rule_1_6_1(ivd: IvdProfile):
    """Schedule 2A clause 1.6(1).

    (1) A reagent or other article that possesses specific characteristics,
    intended by the manufacturer, to make it suitable for in vitro diagnostic
    procedures related to a specific examination is classified as a Class 1
    IVD medical device or a Class 1 in-house IVD medical device.
    """
    rule_id = f"{PREFIX}-1.6(1)"
    value = _lookup(ivd, "is_ancillary_reagent_or_article", rule_id, "1.6(1)")
    if isinstance(value, Pending):
        # No "despite" and the lowest class: it can never outrank another hit.
        return replace(value, ceiling="Class 1 IVD")
    if value is not Tri.YES:
        return None
    return RuleHit(rule_id, cite("1.6(1)"), "Class 1 IVD",
                   _because(ivd, "is_ancillary_reagent_or_article"))


def rule_1_7(ivd: IvdProfile):
    """Schedule 2A clause 1.7.

    An IVD medical device not mentioned in this Schedule is classified as a
    Class 2 IVD medical device or a Class 2 in-house IVD medical device.
    """
    return RuleHit(f"{PREFIX}-1.7", cite("1.7"), "Class 2 IVD",
                   "no other clause of Schedule 2A applies; "
                   + _because(ivd, "is_ancillary_reagent_or_article"))


FALLBACK_READING = Flag(
    severity=Severity.AMBER,
    code="s2a_fallback_reading",
    message=(
        "Classified under the Schedule 2A fallback (clause 1.6(1) or 1.7). "
        "Clause 1.6(1) has been read as covering ancillary reagents and "
        "articles used in a specific examination (buffers, wash solutions, "
        "general reagents), not the test itself; read literally it would make "
        "almost every test Class 1. Confirm that reading before relying on "
        "the class."
    ),
)


def _fallback_flag(result: Classification) -> list[Flag]:
    governing = result.governing
    fallback = {f"{PREFIX}-1.6(1)", f"{PREFIX}-1.7"}
    if governing and all(h.rule_id in fallback for h in governing):
        return [FALLBACK_READING]
    return []


ALL_RULES = [
    rule_1_1_a,
    rule_1_1_b,
    rule_1_2_1,
    rule_1_2_2,
    rule_1_3_a,
    rule_1_3_b,
    rule_1_3_c,
    rule_1_3_d,
    rule_1_3_e,
    rule_1_3_f_i,
    rule_1_3_f_ii,
    rule_1_3_f_iii,
    rule_1_3_fa,
    rule_1_3_g,
    rule_1_3_h,
    rule_1_3_i,
    rule_1_3_j,
    rule_1_4,
    rule_1_5,
    rule_1_6_2_a,
    rule_1_6_2_b,
    rule_1_6_2_c,
    rule_1_6_1,
    rule_1_8,
]


NOTE_1_3_F = Flag(
    severity=Severity.AMBER,
    code="s2a_1_3f_note",
    message=(
        "Classified under Schedule 2A clause 1.3(f). The note to paragraph (f) "
        "says a device like this, other than a companion diagnostic, would fall "
        "into Class 2 under clause 1.7 if a therapy decision would usually be "
        "made only after further investigation, or if the device is used for "
        "monitoring. Check that neither applies before relying on Class 3."
    ),
)


def _note_to_1_3_f(ivd: IvdProfile, result: Classification) -> list[Flag]:
    """Raise the note when 1.3(f) alone decides the class.

    A note explains a clause rather than adding a condition to it, so the
    class stands and a person checks. When another paragraph gives the same
    class, the note could not change the answer and nothing is raised.
    """
    governing = result.governing
    if not governing or not all(h.rule_id.startswith(f"{PREFIX}-1.3(f)(") for h in governing):
        return []
    if known(ivd.is_companion_diagnostic) is Tri.YES:
        return []
    return [NOTE_1_3_F]


# The class each paragraph gives. Clauses 1.5, 1.6(2) and 1.8 open "Despite"
# and are left out: each displaces a higher class, so an unresolved one
# always blocks. 1.6(1) sets its own ceiling; 1.7 only runs once every other
# clause is answered, so it is never pending.
DESPITE = frozenset({f"{PREFIX}-1.5", f"{PREFIX}-1.6(2)(a)", f"{PREFIX}-1.6(2)(b)",
                     f"{PREFIX}-1.6(2)(c)", f"{PREFIX}-1.8"})

CEILINGS = {f"{PREFIX}-{reference}": result for reference, result in {
    "1.1(a)": "Class 4 IVD", "1.1(b)": "Class 4 IVD",
    "1.2(1)": "Class 3 IVD", "1.2(2)": "Class 4 IVD",
    "1.3(a)": "Class 3 IVD", "1.3(b)": "Class 3 IVD", "1.3(c)": "Class 3 IVD",
    "1.3(d)": "Class 3 IVD", "1.3(e)": "Class 3 IVD",
    "1.3(f)(i)": "Class 3 IVD", "1.3(f)(ii)": "Class 3 IVD", "1.3(f)(iii)": "Class 3 IVD",
    "1.3(fa)": "Class 3 IVD", "1.3(g)": "Class 3 IVD", "1.3(h)": "Class 3 IVD",
    "1.3(i)": "Class 3 IVD", "1.3(j)": "Class 3 IVD",
    "1.4": "Class 3 IVD",
    "1.6(1)": "Class 1 IVD",
}.items()}


def evaluate(ivd: IvdProfile) -> Classification:
    outcomes = apply_ceilings([rule(ivd) for rule in ALL_RULES], CEILINGS, DESPITE)
    result = resolve(outcomes, IVD_ORDER)
    live = [h for h in result.hits if h.rule_id not in result.displaced]
    if not live and not result.unresolved:
        # "Not mentioned in this Schedule": every other clause answered, none hit.
        outcomes.append(rule_1_7(ivd))
        result = resolve(outcomes, IVD_ORDER)
    result.flags = _note_to_1_3_f(ivd, result) + _fallback_flag(result)
    return result
