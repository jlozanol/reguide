# reguide

Classification and reimbursement triage for early-stage medical devices in Australia.

Given a plain-language device description, reguide works out the likely TGA
classification with the rule that produced it, then flags which funding pathway
applies and what has to happen first. It produces a draft with its working shown.
It is preparation material, not regulatory advice.

## Scope

- Australia only. TGA classification under the Therapeutic Goods (Medical Devices)
  Regulations 2002, Schedule 2 for general devices and Schedule 2A for IVDs.
- FDA data is used as supporting evidence, not as a second classification engine.
- No patient data. No clinical decision support. Nothing here touches the care itself.

## How it works

1. Intake turns a free-text description into a structured `DeviceProfile`.
2. Missing fields trigger one clarifying question at a time until the profile is complete.
3. Rule engines evaluate every applicable rule and return the full set that fires.
4. Reimbursement triage takes the assigned class and works out channel and tier.
5. Comparable listings and prior assessments are checked against the engine output.
6. A draft pack is assembled, with citations and open questions, for human review.

Steps 3 to 5 contain no model calls. Only intake and report assembly use the API.

## Install

```
python -m venv .venv && source .venv/bin/activate
pip install -e ".[app,dev]"
cp .env.example .env    # add your API keys
```

## Data

Nothing in `data/` is committed. Rebuild it:

```
python scripts/load_artg.py       # ARTG export into SQLite
python scripts/load_mbs.py        # MBS item files
python scripts/load_legislation.py  # Schedules 1, 2 and 2A as clause files
```

## Test

```
pytest
```

`tests/fixtures/` holds device profiles with known classifications. Agreement
against that set is the only quality measure that matters.

## Status

Early. Schedule 2A rules first, Schedule 2 after.
