"""Write the exclusion table the status gate reads.

Source: Therapeutic Goods (Excluded Goods) Determination 2018, Compilation
No. 11 (compilation date 8 August 2024), F2018L01350.

Schedule 1 goods are excluded outright (section 5). Schedule 2 goods are
excluded only when used, advertised or presented for supply in the way its
column 3 describes (section 6). Item numbers repeat across the two Schedules,
so every key carries its Schedule: S1-14B, S2-7.

The summaries are short paraphrases for the report and for intake, not the
legal text. Each names the conditions that have to hold, because the gate's
exclusion_conditions_met answer is a claim that every one of them does. Check
the item in the Determination itself before relying on a summary.

When a new compilation is registered, update the items here and COMPILATION,
then rerun.

Run:  python scripts/build_exclusions.py
"""

import json
from pathlib import Path

OUT = (Path(__file__).resolve().parent.parent
       / "data" / "legislation" / "excluded_goods_determination_2018.json")

INSTRUMENT = "Therapeutic Goods (Excluded Goods) Determination 2018"
COMPILATION = {
    "register_id": "F2018L01350",
    "compilation": 11,
    "compilation_date": "2024-08-08",
}

# (item, software, summary)
SCHEDULE_1 = [
    ("1", False, "Adhesive removers and non-medicated skin cleansers for colostomy "
                 "and ileostomy care"),
    ("1A", False, "Anatomical models intended for education or record keeping"),
    ("2", False, "Antiperspirants whose effect comes only from inorganic salts of "
                 "aluminium, zinc or zirconium"),
    ("2A", False, "Non-sterile personal protective equipment and safety apparel, "
                  "other than articles in item 1 of Schedule 1 to the Specified "
                  "Articles Instrument 2020"),
    ("2B", False, "Cosmetic finishing components for orthoses and prostheses"),
    ("2C", False, "Craniofacial prostheses that are spectacle-retained or "
                  "adhesive-retained"),
    ("3", False, "Dental bleaches and dental whiteners"),
    ("3AA", False, "Dental impression trays"),
    ("3A", False, "Laundry and general cleaning detergents and soaps, other than "
                  "disinfectants"),
    ("4", False, "Devices that measure alcohol in body fluids or exhaled air"),
    ("5", False, "Disinfectant and sterilant gases"),
    ("6", False, "Drinking water purification and treatment equipment"),
    ("7", False, "Ear candles"),
    ("7AA", False, "Ear moulds intended to anchor hearing aids"),
    ("7A", False, "Fluoridated reticulated drinking water"),
    ("8", False, "Hair bleaches, dyes, colorants and perming preparations"),
    ("9", False, "Household and personal aids, furniture and utensils for people "
                 "with disabilities"),
    ("10", False, "Incontinence pads, mattress overlays and mattress protectors"),
    ("10A", False, "Medicament trays intended to hold medicaments"),
    ("11", False, "Menstrual pads, but not tampons or menstrual cups"),
    ("11A", False, "Mouthguards intended to protect teeth from external forces, "
                   "such as in contact sport"),
    ("11B", False, "Ocular prostheses intended for cosmetic purposes"),
    ("11C", False, "Physical impressions of anatomy and models cast from them"),
    ("12", False, "Sanitation, environmental control and detoxification equipment, "
                  "including films and coatings, other than articles in item 3 of "
                  "Schedule 1 to the Specified Articles Instrument 2020; does not "
                  "include disinfectants"),
    ("12A", False, "Spectacle frames"),
    ("13", False, "Nail preparations that harden nails or deter nail biting"),
    ("14", False, "Lip products containing sunscreen that are secondary sunscreen "
                  "products, contain no Schedule 2, 3, 4 or 8 poison, and meet the "
                  "AS/NZS 2604:2021 labelling and broad-spectrum requirements; see "
                  "section 7 for transitional goods"),
    ("14A", True, "Consumer software for self-management of an existing condition "
                  "that is not serious, provided it is not for use in clinical "
                  "practice, not for a serious condition, and not for diagnosis, "
                  "treatment or a specific treatment recommendation"),
    ("14B", True, "Consumer software, alone or with non-invasive hardware, that "
                  "promotes general health or wellness by non-invasively measuring "
                  "or monitoring a physical parameter such as movement, sleep, heart "
                  "rate or rhythm, temperature, blood pressure or oxygen saturation, "
                  "provided it is not for clinical practice and not for any "
                  "diagnostic, monitoring or treatment purpose relating to a serious "
                  "condition"),
    ("14C", True, "Consumer software that coaches or encourages behaviour change on "
                  "personal or environmental factors such as weight, exercise, sun "
                  "exposure or diet, provided it is not for clinical practice, gives "
                  "no information needing a health professional's interpretation, "
                  "and is not for diagnosis, prognosis or treatment decisions"),
    ("14D", True, "Software that is a patient reported outcome measures (PROMs) "
                  "questionnaire or patient survey, provided it is not intended to "
                  "diagnose, screen, monitor, predict, treat or recommend treatment"),
    ("14E", True, "Digital mental health tools, including cognitive behaviour "
                  "therapy tools, based on established clinical practice guidelines "
                  "that the software references and displays so the user can review "
                  "them"),
    ("14F", True, "Software enabling communication, including transmission of "
                  "patient information, to support delivery of health services, "
                  "provided it has no diagnostic, monitoring, predictive or "
                  "treatment purpose"),
    ("14G", True, "Software for administering or managing health processes or "
                  "facilities, such as billing, claims, appointments, bed and theatre "
                  "management, scheduling, business analytics and inventory, provided "
                  "it has no diagnostic, monitoring, predictive or treatment purpose"),
    ("14H", True, "Software whose sole purpose is storing or transmitting patient "
                  "images"),
    ("14I", True, "Software whose sole purpose is alerting health professionals "
                  "about patient care, provided it does not replace clinical "
                  "judgement and is not intended to diagnose, screen, prevent, treat "
                  "or decide treatment"),
    ("14J", True, "Clinical workflow management software, provided it has no "
                  "diagnostic, monitoring, predictive or treatment purpose"),
    ("14K", True, "Middleware connecting applications to an operating system or "
                  "other applications, provided it does not control medical devices, "
                  "does not perform analysis or logic relating to a device's intended "
                  "purpose, and has no diagnostic or treatment purpose"),
    ("14L", True, "Calculator software that either uses published clinical standards "
                  "or authoritative sources, or displays calculations and outputs so "
                  "the user can validate them, provided it does not control the "
                  "administration of a calculated dose"),
    ("14M", True, "Electronic health records used in clinical practice by healthcare "
                  "providers to manage patient clinical data within or between "
                  "facilities, provided they have no diagnostic, monitoring, "
                  "predictive or treatment purpose"),
    ("14N", True, "Data analytics software for collecting and analysing class, group "
                  "or population data, provided it is not for diagnosis, monitoring, "
                  "prediction, prognosis or treatment of individuals"),
    ("14O", True, "Laboratory information management systems, provided they do not "
                  "manipulate data to change or generate diagnostic outputs (beyond "
                  "simple calculations or report comments) and have no monitoring, "
                  "predictive or treatment purpose"),
    ("15", False, "Tinted bases and foundations containing sunscreen that are "
                  "secondary sunscreen products, contain no Schedule 2, 3, 4 or 8 "
                  "poison, and meet the AS/NZS 2604:2021 labelling and broad-spectrum "
                  "requirements; see section 7 for transitional goods"),
]

SCHEDULE_2 = [
    ("1", False, "Anti-acne skin care containing no Schedule 2, 3, 4 or 8 poison, "
                 "when presented as controlling acne only by cleansing, "
                 "moisturising, exfoliating or drying the skin"),
    ("2", False, "Antibacterial skin care containing no Schedule 2, 3, 4 or 8 poison, "
                 "when presented as active against bacteria only, and not for use "
                 "with disease, piercing, blood exposure, clinical contact, "
                 "venepuncture or injections"),
    ("3", False, "Anti-dandruff hair care, when presented as controlling dandruff "
                 "only by cleansing, moisturising, exfoliating or drying the scalp"),
    ("4", False, "Compressed gases, when used as a power source for medical devices"),
    ("4A", False, "Human cells or tissues collected from a patient and manufactured "
                  "under the treating practitioner's supervision in a hospital, when "
                  "used for that patient and not advertised to consumers"),
    ("4B", False, "Fresh viable human haematopoietic progenitor cells, when used for "
                  "direct donor-to-host transplantation for haematopoietic "
                  "reconstitution"),
    ("4C", False, "Fresh viable human organs or parts of organs, when used for direct "
                  "donor-to-host transplantation"),
    ("4D", False, "Human reproductive tissue, when used in assisted reproductive "
                  "therapy"),
    ("4E", False, "Human eggs or sperm, when used in an activity authorised by a "
                  "mitochondrial donation licence"),
    ("5", False, "Moisturising skin care containing sunscreen that is a secondary "
                 "sunscreen product meeting AS/NZS 2604:2021, when presented at SPF "
                 "15 or below, not water-resistant, at most 300 mL or 300 g, with "
                 "an expiry date if needed and no therapeutic claims beyond premature "
                 "ageing"),
    ("6", False, "Oral hygiene products containing no Schedule 2, 3, 4 or 8 poison, "
                 "when the only benefits claimed follow from better oral hygiene, "
                 "including preventing tooth decay"),
    ("7", False, "Packs and kits of medical devices for preventing blood borne and "
                 "sexually transmissible diseases, where every item is already on "
                 "the Register, when supplied as part of an expressly authorised "
                 "government health promotion program"),
    ("8", False, "Piped medical gas systems, when installed and used in compliance "
                 "with AS 2896-2011"),
    ("9", False, "Preparations containing a sunscreening substance whose primary "
                 "purpose is neither sun protection nor another therapeutic purpose, "
                 "when presented without any claimed sun protection factor or other "
                 "therapeutic use"),
    ("10", False, "Sunbathing products containing sunscreen with SPF 4 to 15 that "
                  "are secondary sunscreen products meeting AS/NZS 2604:2021, when "
                  "presented at SPF 15 or below, not water-resistant, at most 300 mL "
                  "or 300 g, with an expiry date if needed and no therapeutic claims "
                  "beyond premature ageing"),
    ("11", False, "Goods for retaining, cushioning or repairing dentures, when "
                  "presented for supply to the ultimate consumer"),
]


def entries():
    for schedule, rows in ((1, SCHEDULE_1), (2, SCHEDULE_2)):
        for item, software, summary in rows:
            yield {
                "key": f"S{schedule}-{item}",
                "schedule": schedule,
                "item": item,
                "citation": f"{INSTRUMENT} Schedule {schedule} item {item}",
                "software": software,
                "summary": summary,
            }


def main():
    items = list(entries())
    keys = [entry["key"] for entry in items]
    assert len(keys) == len(set(keys)), "duplicate key"
    payload = {"instrument": INSTRUMENT, **COMPILATION, "items": items}
    OUT.write_text(json.dumps(payload, indent=2) + "\n")
    software = sum(1 for entry in items if entry["software"])
    print(f"{len(items)} items ({software} software) written to {OUT}")


if __name__ == "__main__":
    main()
