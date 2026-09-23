"""See what intake does with one description.

Offline (no key, no cost): feeds two hand-written model replies for the same
description through the real checks, one careful and one careless, and
prints what each becomes.

    uv run python scripts/try_intake.py

Live (needs OPENAI_API_KEY in .env, one call to gpt-6-sol):

    uv run python scripts/try_intake.py --live "Your product description here"

Add --raw to also print the model's reply exactly as it came back.
"""

import argparse
import json
import sys

from reguide.extract import build_profile
from reguide.profile import Answer

TEXT = (
    "SkinCheck is a smartphone app. It analyses a photo of a mole and tells the "
    "user whether to see a doctor about possible melanoma. It is software only; "
    "nothing is supplied sterile. The app does not store images."
)


def claim(target, value, evidence, index=0):
    return {"function_index": index, "target": target, "value": value, "evidence": evidence}


FUNCTIONS = [{"name": "Mole checker", "name_evidence": "SkinCheck",
              "description": "It analyses a photo of a mole"}]

# What a careful model would return: every claim quotes the text.
GOOD_REPLY = {"functions": FUNCTIONS, "claims": [
    claim("core.product_name", "SkinCheck", "SkinCheck is a smartphone app", -1),
    claim("core.intended_purpose",
          "It analyses a photo of a mole and tells the user whether to see a doctor "
          "about possible melanoma.",
          "It analyses a photo of a mole and tells the user whether to see a doctor "
          "about possible melanoma.", -1),
    claim("function.kind", "general_device", "a smartphone app"),
    claim("function.is_software", "yes", "It is software only"),
    claim("general.diagnoses_or_screens", "yes", "whether to see a doctor about possible melanoma"),
    claim("general.decision_maker", "device_gives_the_decision_to_a_lay_user",
          "tells the user whether to see a doctor"),
    claim("general.records_images_or_anatomical_model", "no", "The app does not store images"),
]}

# What a careless model might return: the same product, six kinds of mistake.
BAD_REPLY = {"functions": FUNCTIONS, "claims": [
    claim("function.kind", "general_device", "a smartphone app"),
    # 1. paraphrase: these words are not in the text
    claim("general.diagnoses_or_screens", "yes", "screens moles for skin cancer"),
    # 2. medical knowledge, and not an option: the text never grades melanoma
    claim("general.condition_severity", "fatal", "possible melanoma"),
    # 3. silence read as "no": the text says nothing about animal material
    claim("general.contains_non_viable_animal_material", "no", "SkinCheck is a smartphone app"),
    # 4. "not a device" guessed from the text
    claim("status.therapeutic_purpose", "no_therapeutic_purpose", "a smartphone app"),
    # 5. the intended purpose rewritten instead of copied
    claim("core.intended_purpose", "Screens moles for melanoma risk.",
          "It analyses a photo of a mole and tells the user whether to see a doctor "
          "about possible melanoma.", -1),
    # 6. two answers to one question
    claim("function.is_software", "yes", "It is software only"),
    claim("function.is_software", "no", "a smartphone app"),
]}


def populated(profile):
    """Every field that holds a value, with its evidence."""
    rows = []
    for dotted in profile.relevant() + [f"funding.{n}" for n in
                                        (profile.funding.model_fields if profile.funding else [])]:
        answer = profile.answer_at(dotted)
        if isinstance(answer, Answer) and answer.resolved:
            value = getattr(answer.value, "value", answer.value)
            rows.append((dotted, value, answer.basis.value, answer.evidence))
    # Stated facts the gating does not ask for yet are kept too; show them.
    for index, function in enumerate(profile.functions):
        for section in ("general", "ivd", "status"):
            part = getattr(function, section)
            if part is None:
                continue
            for name in type(part).model_fields:
                dotted = f"functions.{index}.{section}.{name}"
                answer = getattr(part, name)
                if answer.resolved and dotted not in [r[0] for r in rows]:
                    value = getattr(answer.value, "value", answer.value)
                    rows.append((dotted + "  (kept, not asked yet)", value,
                                 answer.basis.value, answer.evidence))
    return rows


def show(title, reply, text):
    profile, rejections = build_profile(reply, text)
    print(f"\n=== {title} ===")
    print("\nKept (goes into the profile):")
    for dotted, value, basis, evidence in populated(profile):
        print(f"  {dotted} = {value!r}  [{basis}]  evidence: {evidence!r}")
    print("\nDropped (never reaches the profile):")
    if not rejections:
        print("  nothing")
    for r in rejections:
        print(f"  {r.target} = {r.value!r}  reason: {r.reason.value}")
        print(f"      evidence given: {r.evidence!r}")
    print(f"\nUntraceable evidence: {profile.untraceable_evidence() or 'none'}")
    missing = profile.askable()
    print(f"Still to ask the founder: {len(missing)} fields, starting with:")
    for name in missing[:6]:
        print(f"  {name}")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--live", metavar="TEXT", help="send TEXT to the model")
    parser.add_argument("--raw", action="store_true", help="print the model's reply too")
    args = parser.parse_args(argv)

    if args.live:
        from reguide.llm import IntakeError, OpenAIIntake

        client = OpenAIIntake()
        print(f"Calling {client.model} (reasoning off, temperature 0)...")
        try:
            reply = client.complete(args.live)
        except IntakeError as error:
            print(f"The model's reply was unusable: {error}")
            return 1
        if args.raw:
            print(json.dumps(reply, indent=2))
        show("Live reply", reply, args.live)
        return 0

    print(f"Description:\n  {TEXT}")
    if args.raw:
        print(json.dumps(GOOD_REPLY, indent=2))
    show("A careful reply", GOOD_REPLY, TEXT)
    show("A careless reply", BAD_REPLY, TEXT)
    return 0


if __name__ == "__main__":
    sys.exit(main())
