"""Read the clause files written by scripts/load_legislation.py.

Keyword lookup only. The corpus is under a hundred short files, so matching
words is enough and every hit is a whole clause with its exact citation.

The files are local and gitignored. An empty corpus is reported as empty,
never as "no clause matches", for the same reason the status gate treats an
unloaded source as unknown rather than negative.
"""

import re
from dataclasses import dataclass
from pathlib import Path

CORPUS_DIR = Path(__file__).resolve().parent.parent / "data" / "legislation"
CLAUSE_FILE = re.compile(r"^s(1|2|2a)-.+\.md$")


@dataclass(frozen=True)
class Clause:
    id: str               # "s2a-1.6"
    schedule: str         # "2A"
    clause: str           # "1.6"
    heading: str
    citation: str
    compilation: int
    compilation_date: str
    text: str             # the body, without front matter
    path: Path


class CorpusMissing(RuntimeError):
    """No clause files. Run scripts/load_legislation.py first."""


def _parse(path: Path) -> Clause:
    raw = path.read_text(encoding="utf-8")
    if not raw.startswith("---\n"):
        raise ValueError(f"{path.name}: no front matter")
    front, body = raw[4:].split("\n---\n", 1)
    meta = dict(line.split(": ", 1) if ": " in line else (line.rstrip(":"), "")
                for line in front.splitlines())
    return Clause(
        id=meta["id"],
        schedule=meta["schedule"],
        clause=meta["clause"],
        heading=meta["heading"],
        citation=meta["citation"],
        compilation=int(meta["compilation"]),
        compilation_date=meta["compilation_date"],
        text=body.strip(),
        path=path,
    )


def load(directory: str | Path = CORPUS_DIR) -> dict[str, Clause]:
    """Every clause file in the folder, keyed by id."""
    paths = [p for p in sorted(Path(directory).glob("*.md")) if CLAUSE_FILE.match(p.name)]
    if not paths:
        raise CorpusMissing(
            f"no clause files in {directory}; run scripts/load_legislation.py"
        )
    clauses = {}
    for path in paths:
        clause = _parse(path)
        if path.stem != clause.id:
            raise ValueError(f"{path.name} declares id {clause.id}")
        clauses[clause.id] = clause
    return clauses


def find(clauses: dict[str, Clause], *keywords: str) -> list[Clause]:
    """Clauses whose heading or text holds every keyword, case-insensitive.

    Ranked by how often the keywords occur, most first, then by id so the
    order is stable.
    """
    words = [k.lower() for k in keywords if k.strip()]
    if not words:
        return []
    scored = []
    for clause in clauses.values():
        haystack = f"{clause.heading}\n{clause.text}".lower()
        counts = [haystack.count(word) for word in words]
        if all(counts):
            scored.append((-sum(counts), clause.id, clause))
    return [clause for _, _, clause in sorted(scored)]
