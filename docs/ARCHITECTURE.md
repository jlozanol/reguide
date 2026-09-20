# Architecture notes

## Why the rules are not in the model

Classification under Schedule 2 and Schedule 2A is a decision procedure written
into law. Given the right inputs it has one correct answer and a clause that
produces it. Code gives you that plus a test suite. A language model gives you a
plausible answer you cannot verify, which is worthless in this domain.

The model does two jobs only: reading a messy description into a structured
profile, and writing the result up in readable prose. Both are language tasks.

## Why unknown is a value

Every yes/no field in the profile is three-state. A False default on a field the
founder never mentioned produces a confident wrong class. The rule engine refuses
to evaluate while a relevant field is unresolved.

## Why classification runs before reimbursement

The Prescribed List tier depends on the device class. Tier 1 is limited to Class
IIb and below with well-established technology; Class III and Part C devices go to
Tier 2; novel technologies go to full assessment. Reimbursement triage cannot run
without the class, so the pipeline is sequential rather than parallel.

## Why disagreement is surfaced, not resolved

When the engine and comparable ARTG listings disagree, the tool reports both. The
cause might be an engine bug, a genuine difference in the device, or comparators
classified under earlier rules. None of those can be settled automatically, and
hiding the discrepancy would remove the most useful line in the output.

## Handling of submitted descriptions

Device descriptions are commercially sensitive and often pre-publication. Inputs
are not logged by default. A local-run path exists so nothing leaves the machine.
