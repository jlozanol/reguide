"""Build the fixture set.

Fixtures marked verified=true come from a TGA worked example, so the expected
class arrives with the rule that produces it. Fixtures marked verified=false
are reasoned from rule text rather than quoted from an example, or sit on a
point where sources disagree. The scoring harness counts only verified ones.
Promote a fixture to verified after checking it against the primary document.

Run:  python scripts/build_fixtures.py
"""

import json
from pathlib import Path

from reguide.profile import (
    ActiveType,
    Answer,
    Basis,
    BodyContact,
    ClinicalFunction,
    CoreProfile,
    DecisionMaker,
    DeviceKind,
    DeviceProfile,
    Duration,
    FluidHandling,
    FunctionProfile,
    GeneralDeviceProfile,
    highest_class,
    Invasiveness,
    IvdProfile,
    IvdPurpose,
    OrificeSite,
    PublicHealthRisk,
    Severity,
    Tri,
    WoundFunction,
)

OUT = Path(__file__).resolve().parent.parent / "tests" / "fixtures"
NOT_IVD = "TGA, Classifying medical devices that are not IVDs"
ACTIVE = "TGA, Classifying active medical devices in Australia"
IVD_GUIDE = "TGA, Classifying IVDs for supply in Australia"
RULE_TEXT = "Reasoned from Schedule 2 rule text, not a worked example"


def a(value, evidence):
    return Answer(value=value, basis=Basis.STATED, evidence=evidence)


GENERAL_DEFAULTS = dict(
    invasiveness=Invasiveness.NON_INVASIVE,
    active_type=ActiveType.NOT_ACTIVE,
    incorporates_medicine=Tri.NO,
    contraceptive_or_sti_prevention=Tri.NO,
    disinfects_another_device=Tri.NO,
    animal_or_microbial_origin=Tri.NO,
    human_blood_derivative=Tri.NO,
    contacts_injured_skin=Tri.NO,
    fluid_handling=FluidHandling.NONE,
)

IVD_DEFAULTS = dict(
    is_instrument_or_receptacle=Tri.NO,
    is_quality_control_material=Tri.NO,
    is_export_only=Tri.NO,
    purpose=IvdPurpose.OTHER,
    is_self_test=Tri.NO,
    is_near_patient_test=Tri.NO,
    detects_transmissible_agent=Tri.NO,
    transmission_risk_to_population=Tri.NO,
    disease_is_life_threatening=Tri.NO,
    result_drives_critical_decision=Tri.NO,
    sample_type="not stated",
)


def fn(name, text, **given):
    """One general-device function."""
    software = given.pop("software", Tri.NO)
    fields = dict(GENERAL_DEFAULTS)
    fields.update(given)
    if software is Tri.YES:
        for key in ("animal_or_microbial_origin", "human_blood_derivative"):
            fields.pop(key, None)
    return FunctionProfile(
        name=a(name, name),
        description=a(text, text),
        kind=a(DeviceKind.GENERAL, text),
        is_software=a(software, text),
        general=GeneralDeviceProfile(**{k: a(v, text) for k, v in fields.items()}),
    )


def ivd_fn(name, text, **given):
    """One IVD function."""
    fields = dict(IVD_DEFAULTS)
    fields.update(given)
    return FunctionProfile(
        name=a(name, name),
        description=a(text, text),
        kind=a(DeviceKind.IVD, text),
        is_software=a(given.pop("software", Tri.NO), text),
        ivd=IvdProfile(**{k: a(v, text) for k, v in fields.items()}),
    )


def product(name, text, functions, sterile=Tri.NO, measuring=Tri.NO):
    """Assemble a product and prune each function to what gating asks for.

    source_text is everything the founder would have written, so every piece
    of evidence in the fixture really is a phrase from the source.
    """
    confirmation = "fixture decomposition is fixed by hand"
    parts = [name, text] + [
        f"{f.name.value} {f.description.value}" for f in functions
    ] + [confirmation]
    source_text = " ".join(parts)

    core = CoreProfile(
        product_name=a(name, name),
        intended_purpose=a(text, text),
        supplied_sterile=a(sterile, text),
        has_measuring_function=a(measuring, text),
        functions_confirmed=a(Tri.YES, confirmation),
    )
    return DeviceProfile(
        core=core,
        functions=[f.prune() for f in functions],
        source_text=source_text,
    )


def device(name, text, **given):
    """A single-function general device product. The common case."""
    sterile = given.pop("sterile", Tri.NO)
    measuring = given.pop("measuring", Tri.NO)
    return product(name, text, [fn(name, text, **given)],
                   sterile=sterile, measuring=measuring)


def ivd(name, text, **given):
    """A single-function IVD product."""
    return product(name, text, [ivd_fn(name, text, **given)])


F = []


def add(slug, expected, rule, source, note, profile, verified=True):
    """A single-function fixture. The expectation applies to function 0."""
    F.append((slug, source, note, profile, verified, [(expected, rule)]))


def add_multi(slug, source, note, profile, expectations, verified=False):
    """A multi-function fixture. One expectation per function, in order.

    The product-level answer is derived, not asserted: the highest class per
    family. Asserting it separately would let the fixture disagree with itself.
    """
    assert len(expectations) == len(profile.functions), slug
    F.append((slug, source, note, profile, verified, expectations))


# -- The screw family. One device, three classes. ---------------------------
add("screw_transient", "Class IIa", "3.2(2)", NOT_IVD,
    "Transient use during surgery.",
    device("Metal fixation screw, intraoperative",
           "Holds bone together temporarily during surgery.",
           invasiveness=Invasiveness.SURGICALLY_INVASIVE, duration=Duration.TRANSIENT,
           body_contact=BodyContact.BREACHED_SKIN, absorbed_or_chemically_changed=Tri.NO,
           reusable_surgical_instrument=Tri.NO, sterile=Tri.YES))

add("screw_short_term", "Class IIa", "3.3(2)", NOT_IVD,
    "Up to 30 days. Same class as transient, different rule.",
    device("Metal fixation screw, short term",
           "Holds bone together for up to 30 days to support fracture healing.",
           invasiveness=Invasiveness.SURGICALLY_INVASIVE, duration=Duration.SHORT_TERM,
           body_contact=BodyContact.BREACHED_SKIN, absorbed_or_chemically_changed=Tri.NO,
           sterile=Tri.YES))

add("screw_long_term", "Class IIb", "3.4(2)", NOT_IVD,
    "Crossing 30 days moves the class. The duration band is load-bearing.",
    device("Metal fixation screw, permanent",
           "Holds bone together for longer than 30 days, permanently implanted.",
           invasiveness=Invasiveness.IMPLANTABLE, duration=Duration.LONG_TERM,
           body_contact=BodyContact.BREACHED_SKIN, absorbed_or_chemically_changed=Tri.NO,
           is_active_implantable=Tri.NO, sterile=Tri.YES))

add("screw_central_circulation", "Class III", "3.3(4)(a)", NOT_IVD,
    "Location beats duration. Tests that body_contact is read first.",
    device("Fixation screw contacting central circulatory system",
           "Direct contact with the central circulatory or central nervous system.",
           invasiveness=Invasiveness.SURGICALLY_INVASIVE, duration=Duration.SHORT_TERM,
           body_contact=BodyContact.CENTRAL_CIRCULATION,
           absorbed_or_chemically_changed=Tri.NO, sterile=Tri.YES))

# -- The dressing family. Intended function decides, not the wound. ---------
add("dressing_mechanical_barrier", "Class I", "2.4(3)", NOT_IVD,
    "Barrier, compression or absorption only. The floor of sub-rule 2.4.",
    device("Absorbent pad",
           "Acts as a barrier to and absorbs exudate from a wound.",
           contacts_injured_skin=Tri.YES,
           wound_function=WoundFunction.MECHANICAL_BARRIER))

add("dressing_microenvironment", "Class IIa", "2.4(1)", NOT_IVD,
    "Same contact as the barrier pad. Only the claim differs.",
    device("Negative wound therapy dressing bandage",
           "Used together with an active medical device to manage the "
           "microenvironment of a wound.",
           contacts_injured_skin=Tri.YES,
           wound_function=WoundFunction.MICROENVIRONMENT,
           connected_to_active_device=Tri.YES))

add("dressing_secondary_intent", "Class IIb", "2.4(4)", NOT_IVD,
    "Breached dermis healing by secondary intent. Top of sub-rule 2.4.",
    device("Dressing for chronic extensive ulceration",
           "For wounds that have breached the dermis and can only heal by "
           "secondary intent.",
           contacts_injured_skin=Tri.YES,
           wound_function=WoundFunction.SECONDARY_INTENT,
           breaches_dermis=Tri.YES, sterile=Tri.YES))

add("dressing_collagen_deep_wound", "Class IIb", "2.4(4)", NOT_IVD,
    "SOURCES CONFLICT. A TGA case study puts a collagen dressing for breached "
    "dermis at 2.4(4) Class IIb, while collagen dressings also appear in a "
    "Class III list under the animal origin rule. Resolve from the primary "
    "document before trusting either value.",
    device("Collagen dressing for deep ulcers",
           "Dressing for deep wounds and ulcers that have breached the dermis, "
           "containing collagen for wound healing.",
           contacts_injured_skin=Tri.YES,
           wound_function=WoundFunction.SECONDARY_INTENT,
           breaches_dermis=Tri.YES, animal_or_microbial_origin=Tri.YES,
           sterile=Tri.YES),
    verified=False)

add("trauma_covering_anaesthetic", "Class III", "5.1(2)", NOT_IVD,
    "A medicine overrides sub-rule 2.4 entirely. Tests special-rule priority.",
    device("Trauma covering with anaesthetic gel",
           "Non-sterile trauma covering to maintain stability of a burn patient "
           "en route to hospital, coated in a gel containing anaesthetic.",
           contacts_injured_skin=Tri.YES,
           wound_function=WoundFunction.MECHANICAL_BARRIER,
           incorporates_medicine=Tri.YES))

add("heparin_coated_catheter", "Class III", "5.1", NOT_IVD,
    "Incorporated medicine lifts an otherwise lower-class catheter.",
    device("Heparin-coated catheter",
           "Catheter incorporating heparin as an ancillary medicinal substance.",
           invasiveness=Invasiveness.SURGICALLY_INVASIVE, duration=Duration.SHORT_TERM,
           body_contact=BodyContact.CENTRAL_CIRCULATION,
           absorbed_or_chemically_changed=Tri.NO,
           incorporates_medicine=Tri.YES, sterile=Tri.YES))

add("condom_with_spermicide", "Class III", "5.2", NOT_IVD,
    "Contraception plus a medicine. A plain condom sits lower.",
    device("Condom with spermicide",
           "Barrier contraceptive incorporating a spermicidal agent.",
           invasiveness=Invasiveness.BODY_ORIFICE, duration=Duration.TRANSIENT,
           orifice_site=OrificeSite.OTHER_ORIFICE, connected_to_active_device=Tri.NO,
           contraceptive_or_sti_prevention=Tri.YES, incorporates_medicine=Tri.YES))

# -- Orifice route ----------------------------------------------------------
add("orifice_long_term", "Class IIb", "3.1(2)(c)(i)", NOT_IVD,
    "Long-term use through a body orifice.",
    device("Long-term indwelling orifice device",
           "Invasive device used through a body orifice for longer than 30 days.",
           invasiveness=Invasiveness.BODY_ORIFICE, duration=Duration.LONG_TERM,
           orifice_site=OrificeSite.OTHER_ORIFICE, connected_to_active_device=Tri.NO))

# -- Active devices ---------------------------------------------------------
add("diagnostic_ultrasound", "Class IIa", "4.3(2)(a)", ACTIVE,
    "Supplies energy absorbed by the body for diagnosis.",
    device("General purpose diagnostic ultrasound",
           "Supplies ultrasonic energy absorbed by the patient for imaging.",
           active_type=ActiveType.DIAGNOSTIC, clinical_function=ClinicalFunction.SUPPLY_ENERGY,
           delivers_hazardous_energy=Tri.NO, delivers_ionising_radiation=Tri.NO,
           records_diagnostic_images=Tri.YES, body_contact=BodyContact.INTACT_SKIN))

add("mri_equipment", "Class IIa", "4.3(2)(a)", ACTIVE,
    "Same rule as ultrasound. Confirms the rule is not imaging-modality specific.",
    device("Magnetic resonance equipment",
           "Supplies energy absorbed by the patient's body for diagnostic imaging.",
           active_type=ActiveType.DIAGNOSTIC, clinical_function=ClinicalFunction.SUPPLY_ENERGY,
           delivers_hazardous_energy=Tri.NO, delivers_ionising_radiation=Tri.NO,
           records_diagnostic_images=Tri.YES, body_contact=BodyContact.NONE))

add("radiotherapy_afterloading_control", "Class IIb", "4.3(3)(c)", ACTIVE,
    "Controls a device that emits ionising radiation. Control inherits the risk.",
    device("Radiotherapy after-loading control system",
           "Controls and monitors the performance of a device emitting ionising "
           "radiation for therapeutic interventional radiology.",
           active_type=ActiveType.DIAGNOSTIC,
           clinical_function=ClinicalFunction.CONTROL_ANOTHER_DEVICE,
           delivers_hazardous_energy=Tri.YES, delivers_ionising_radiation=Tri.YES,
           records_diagnostic_images=Tri.NO, body_contact=BodyContact.NONE))

# -- Software. The pairs that matter most. ----------------------------------
add("melanoma_screening_app", "Class III", "4.5(1)(c)(i)", ACTIVE,
    "Device gives the screening decision to a consumer, condition can kill "
    "without urgent treatment.",
    device("Consumer melanoma screening app",
           "Analyses an image of a mole to screen for malignant melanoma, giving "
           "the screening decision to the consumer.",
           software=Tri.YES, active_type=ActiveType.DIAGNOSTIC,
           clinical_function=ClinicalFunction.DIAGNOSE_OR_SCREEN,
           decision_maker=DecisionMaker.DEVICE_TO_LAY_USER,
           condition_severity=Severity.DEATH_WITHOUT_URGENT_TREATMENT,
           public_health_risk=PublicHealthRisk.LOW,
           delivers_hazardous_energy=Tri.NO, delivers_ionising_radiation=Tri.NO,
           records_diagnostic_images=Tri.NO, body_contact=BodyContact.NONE))

add("emphysema_ct_software", "Class IIa", "4.5(2)(b)", ACTIVE,
    "Same rule family as the melanoma app. A clinician decides, so it drops.",
    device("Emphysema detection software",
           "Diagnoses emphysema from CT scans, providing information to a health "
           "professional to support diagnostic decision making.",
           software=Tri.YES, active_type=ActiveType.DIAGNOSTIC,
           clinical_function=ClinicalFunction.DIAGNOSE_OR_SCREEN,
           decision_maker=DecisionMaker.INFORMS_PROFESSIONAL,
           condition_severity=Severity.SERIOUS,
           public_health_risk=PublicHealthRisk.MODERATE,
           delivers_hazardous_energy=Tri.NO, delivers_ionising_radiation=Tri.NO,
           records_diagnostic_images=Tri.NO, body_contact=BodyContact.NONE))

add("spect_cardiac_monitoring", "Class IIb", "4.6(a)", ACTIVE,
    "Monitoring where the information could indicate immediate danger.",
    device("SPECT cardiac monitoring software",
           "Analyses gamma camera imagery from a SPECT scan to track progression "
           "of heart disease from cardiac muscle blood flow.",
           software=Tri.YES, active_type=ActiveType.DIAGNOSTIC,
           clinical_function=ClinicalFunction.MONITOR,
           decision_maker=DecisionMaker.INFORMS_PROFESSIONAL,
           condition_severity=Severity.DEATH_WITHOUT_URGENT_TREATMENT,
           public_health_risk=PublicHealthRisk.LOW,
           delivers_hazardous_energy=Tri.NO, delivers_ionising_radiation=Tri.NO,
           records_diagnostic_images=Tri.NO, body_contact=BodyContact.NONE))

add("emg_dystrophy_monitoring", "Class IIa", "4.6(b)", ACTIVE,
    "Paired with the SPECT fixture. Same rule, lower danger, lower class.",
    device("Muscle response monitoring app",
           "Receives electromyography data by Bluetooth to monitor muscle fibre "
           "response in a person with muscular dystrophy.",
           software=Tri.YES, active_type=ActiveType.DIAGNOSTIC,
           clinical_function=ClinicalFunction.MONITOR,
           decision_maker=DecisionMaker.INFORMS_PROFESSIONAL,
           condition_severity=Severity.MODERATE,
           public_health_risk=PublicHealthRisk.LOW,
           delivers_hazardous_energy=Tri.NO, delivers_ionising_radiation=Tri.NO,
           records_diagnostic_images=Tri.NO, body_contact=BodyContact.NONE))

# -- Class I sub-classes. Not quoted from a worked example. -----------------
add("sterile_barrier_dressing", "Class Is", "2.4(3) with sterile supply", RULE_TEXT,
    "Identical to dressing_mechanical_barrier except for sterile supply.",
    device("Sterile absorbent pad",
           "Acts as a barrier to and absorbs exudate from a wound, supplied sterile.",
           contacts_injured_skin=Tri.YES,
           wound_function=WoundFunction.MECHANICAL_BARRIER, sterile=Tri.YES),
    verified=False)

add("measuring_thermometer", "Class Im", "2.1 with measuring function", RULE_TEXT,
    "Exercises has_measuring_function, which nothing else in the set touches.",
    device("Non-invasive clinical thermometer",
           "Measures body temperature by contact with intact skin.",
           body_contact=BodyContact.INTACT_SKIN, measuring=Tri.YES),
    verified=False)

add("reusable_surgical_instrument", "Class I", "3.2(3)", RULE_TEXT,
    "A reusable instrument drops to Class I despite surgical invasiveness.",
    device("Reusable surgical scissors",
           "Reusable surgical instrument for transient use during surgery.",
           invasiveness=Invasiveness.SURGICALLY_INVASIVE, duration=Duration.TRANSIENT,
           body_contact=BodyContact.BREACHED_SKIN, absorbed_or_chemically_changed=Tri.NO,
           reusable_surgical_instrument=Tri.YES),
    verified=False)

# -- IVDs, Schedule 2A ------------------------------------------------------
add("culture_media", "Class 1 IVD", "1.6", IVD_GUIDE,
    "Named exception. Cannot be reasoned to, only looked up.",
    ivd("Microbiological culture medium",
        "Prepared culture medium for microbiological laboratory use.",
        is_instrument_or_receptacle=Tri.YES))

add("prothrombin_meter", "Class 1 IVD", "1.6", IVD_GUIDE,
    "The meter is Class 1 while its own test strips are Class 3. Pairs with "
    "prothrombin_self_test to test that the pack is split, not merged.",
    ivd("Portable prothrombin time meter",
        "Instrument that reads prothrombin time test strips.",
        is_instrument_or_receptacle=Tri.YES))

add("quality_control_material", "Class 2 IVD", "1.5", IVD_GUIDE,
    "Non-assay-specific control material. Another named exception.",
    ivd("Non-assay-specific control plasma",
        "Quality control material for coagulation studies, not assay specific.",
        is_quality_control_material=Tri.YES))

add("prothrombin_self_test", "Class 3 IVD", "1.4", IVD_GUIDE,
    "Self-testing lifts the class of the strips above their own meter.",
    ivd("Prothrombin time self-test strips",
        "Test strips for prothrombin time self-testing by a lay person at home.",
        purpose=IvdPurpose.MONITORING, is_self_test=Tri.YES,
        result_drives_critical_decision=Tri.YES, sample_type="capillary whole blood"))

add("hiv_donor_screening", "Class 4 IVD", "1.1", IVD_GUIDE,
    "The IVD ceiling. Donor screening for a high public health risk agent.",
    ivd("HIV blood donor screening assay",
        "Screens donated blood for HIV before transfusion.",
        purpose=IvdPurpose.BLOOD_OR_TISSUE_SCREENING, detects_transmissible_agent=Tri.YES,
        transmission_risk_to_population=Tri.YES, disease_is_life_threatening=Tri.YES,
        result_drives_critical_decision=Tri.YES, sample_type="donor whole blood"))

add("chlamydia_test", "Class 3 IVD", "1.3", IVD_GUIDE,
    "Transmissible agent at moderate rather than high public health risk.",
    ivd("Chlamydia trachomatis assay",
        "Detects Chlamydia trachomatis in a clinical specimen for diagnosis.",
        purpose=IvdPurpose.TRANSMISSIBLE_AGENT, detects_transmissible_agent=Tri.YES,
        transmission_risk_to_population=Tri.NO, disease_is_life_threatening=Tri.NO,
        result_drives_critical_decision=Tri.YES, sample_type="urine or swab"))


add("infusion_pump", "Class IIb", "4.4(2)", ACTIVE,
    "Reaches administers_or_removes_medicine, which nothing else touches. "
    "Potentially hazardous administration lifts it above the 4.4 baseline.",
    device("Volumetric infusion pump",
           "Administers medicines to a patient at a controlled rate, where the "
           "manner of administration is potentially hazardous.",
           active_type=ActiveType.THERAPEUTIC,
           clinical_function=ClinicalFunction.ADMINISTER_SUBSTANCE,
           administers_or_removes_medicine=Tri.YES,
           delivers_hazardous_energy=Tri.YES),
    verified=False)


# -- Multi-function products. The reason functions are first-class. ---------
add_multi(
    "prothrombin_self_test_pack",
    IVD_GUIDE,
    "A procedure pack holding three functions in two rule families. The pack "
    "does not take one class: the meter and strips classify separately as "
    "IVDs and the lancet as a general device.",
    product(
        "Prothrombin time self-testing pack",
        "Procedure pack for prothrombin time self-testing at home, containing "
        "a portable meter, test strips and a lancet.",
        [
            ivd_fn("Portable prothrombin time meter",
                   "Instrument that reads prothrombin time test strips.",
                   is_instrument_or_receptacle=Tri.YES),
            ivd_fn("Prothrombin time test strips",
                   "Test strips for prothrombin time self-testing by a lay person.",
                   purpose=IvdPurpose.MONITORING, is_self_test=Tri.YES,
                   result_drives_critical_decision=Tri.YES,
                   sample_type="capillary whole blood"),
            fn("Lancet",
               "Single-use lancet for obtaining a capillary blood specimen.",
               invasiveness=Invasiveness.SURGICALLY_INVASIVE,
               duration=Duration.TRANSIENT, body_contact=BodyContact.BREACHED_SKIN,
               absorbed_or_chemically_changed=Tri.NO,
               reusable_surgical_instrument=Tri.NO),
        ],
        sterile=Tri.YES,
    ),
    [("Class 1 IVD", "1.6"), ("Class 3 IVD", "1.4"), ("Class IIa", "3.2")],
    verified=True,
)

add_multi(
    "imaging_platform",
    RULE_TEXT,
    "Three software functions of one platform. Storage alone carries no "
    "medical-device purpose, triage flags abnormal studies, and the follow-up "
    "suggestion specifies an intervention. Tests that the highest function "
    "governs the product and that one regulated function is enough to pull "
    "the whole platform in.",
    product(
        "Radiology reporting platform",
        "Stores radiology studies, flags abnormal ones for priority review and "
        "suggests a follow-up imaging interval.",
        [
            fn("Study archive",
               "Stores and displays radiology studies without interpretation.",
               software=Tri.YES, active_type=ActiveType.NOT_ACTIVE,
               body_contact=BodyContact.NONE),
            fn("Abnormality triage",
               "Flags studies showing suspected abnormality for priority review "
               "by a radiologist.",
               software=Tri.YES, active_type=ActiveType.DIAGNOSTIC,
               clinical_function=ClinicalFunction.DIAGNOSE_OR_SCREEN,
               decision_maker=DecisionMaker.INFORMS_PROFESSIONAL,
               condition_severity=Severity.SERIOUS,
               public_health_risk=PublicHealthRisk.MODERATE,
               delivers_hazardous_energy=Tri.NO, delivers_ionising_radiation=Tri.NO,
               records_diagnostic_images=Tri.NO, body_contact=BodyContact.NONE),
            fn("Follow-up interval suggestion",
               "Suggests a follow-up imaging interval to the reporting radiologist.",
               software=Tri.YES, active_type=ActiveType.DIAGNOSTIC,
               clinical_function=ClinicalFunction.SPECIFY_THERAPY,
               decision_maker=DecisionMaker.INFORMS_PROFESSIONAL,
               condition_severity=Severity.SERIOUS,
               public_health_risk=PublicHealthRisk.MODERATE,
               delivers_hazardous_energy=Tri.NO, delivers_ionising_radiation=Tri.NO,
               records_diagnostic_images=Tri.NO, body_contact=BodyContact.NONE),
        ],
    ),
    [("Class I", "not a medical device purpose"),
     ("Class IIa", "4.5(2)(b)"),
     ("Class IIa", "4.7(2)(b)(i)")],
    verified=False,
)

add_multi(
    "wellness_app_with_symptom_checker",
    RULE_TEXT,
    "A consumer app whose main function would be excluded on its own. The "
    "symptom checker is not excluded, and a product is only excluded when "
    "every function qualifies, so the whole app is pulled into regulation. "
    "This is the unanimity test rather than the maximum test.",
    product(
        "Consumer wellbeing app",
        "Tracks sleep and activity for general wellbeing and includes a symptom "
        "checker that suggests whether to seek care.",
        [
            fn("Activity and sleep tracking",
               "Records sleep and activity for general wellbeing.",
               software=Tri.YES, active_type=ActiveType.NOT_ACTIVE,
               body_contact=BodyContact.NONE),
            fn("Symptom checker",
               "Asks a consumer about symptoms and suggests whether to seek "
               "medical care.",
               software=Tri.YES, active_type=ActiveType.DIAGNOSTIC,
               clinical_function=ClinicalFunction.DIAGNOSE_OR_SCREEN,
               decision_maker=DecisionMaker.DEVICE_TO_LAY_USER,
               condition_severity=Severity.MODERATE,
               public_health_risk=PublicHealthRisk.LOW,
               delivers_hazardous_energy=Tri.NO, delivers_ionising_radiation=Tri.NO,
               records_diagnostic_images=Tri.NO, body_contact=BodyContact.NONE),
        ],
    ),
    [("Class I", "not a medical device purpose"), ("Class IIa", "4.5(2)")],
    verified=False,
)


def main():
    OUT.mkdir(parents=True, exist_ok=True)

    # The directory is rebuilt, not added to. A renamed fixture would otherwise
    # leave its old file behind, and stale fixtures fail against a newer schema
    # in ways that look like schema bugs.
    written = {f"{slug}.json" for slug, *_ in F}
    for stale in OUT.glob("*.json"):
        if stale.name not in written:
            stale.unlink()
            print(f"   removed stale fixture {stale.name}")

    gaps = 0
    for slug, source, note, profile, verified, expectations in F:
        missing = profile.missing()
        gaps += len(missing)
        functions = [
            {
                "name": function.name.value,
                "expected_class": expected,
                "expected_rule": rule,
            }
            for function, (expected, rule) in zip(profile.functions, expectations)
        ]
        payload = {
            "expected_classes": highest_class(e for e, _ in expectations),
            "functions": functions,
            "source": source,
            "verified": verified,
            "note": note,
            "profile": profile.model_dump(mode="json"),
        }
        (OUT / f"{slug}.json").write_text(json.dumps(payload, indent=2) + "\n")
        flag = "  " if verified else " ?"
        count = f"{len(functions)} fn" if len(functions) > 1 else "     "
        summary = ", ".join(sorted(payload["expected_classes"].values()))
        warn = f"  MISSING: {missing}" if missing else ""
        print(f"{flag} {slug:34} {count} {summary}{warn}")

    verified_count = sum(1 for f in F if f[4])
    multi = sum(1 for f in F if len(f[5]) > 1)
    print(f"\n{len(F)} fixtures, {verified_count} verified, {multi} multi-function, "
          f"{gaps} unresolved fields")


if __name__ == "__main__":
    main()
