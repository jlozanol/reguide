"""Split the Regulations into one markdown file per clause.

Source: Therapeutic Goods (Medical Devices) Regulations 2002, register
F2002B00237, the Word version from legislation.gov.au. Schedules 1, 2 and 2A
only: the essential principles, the classification rules for general devices
and the classification rules for IVDs.

Clause-level files keep citations exact and make the corpus small enough that
keyword lookup is sufficient. No vector store. reguide/legislation.py reads the
files back.

One file per clause, named by the same schedule-qualified id the rule engines
use: s1-12.1.md, s2-4.5.md, s2a-1.6.md. Clause numbers repeat across Schedules,
so an unqualified id never appears. Schedule 1 has group headings with no text
of their own (7, 8, 9, 11, 12, 13, 13A, 13C); they are recorded on the clauses
under them, not written as files.

The body text is the legislation verbatim, including its own punctuation.
Nothing is paraphrased. Only layout is translated: paragraphs become list
items so (i) the paragraph and (i) the subparagraph stay distinguishable,
notes become quotes and tables become markdown tables.

The compilation number and date are read from the document itself, never
assumed. CHECKED_COMPILATION is the compilation the rule code was last checked
against; loading a different one prints a warning, and the test suite fails
until someone rechecks the rules and updates it.

Standard library only, so rebuilding the corpus needs no extra install.

Run:  uv run python scripts/load_legislation.py
"""

import argparse
import re
import sys
import zipfile
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "data" / "legislation"
SOURCE = OUT_DIR / "source" / "medical_devices_regulations_2002.docx"

INSTRUMENT = "Therapeutic Goods (Medical Devices) Regulations 2002"
# The Word file does not carry its own register id.
REGISTER_ID = "F2002B00237"
CHECKED_COMPILATION = 72

# Schedule id as printed -> file prefix.
SCHEDULES = {"1": "s1", "2": "s2", "2A": "s2a"}

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"

SCHEDULE_HEAD = re.compile(r"^Schedule (\w+)\s*\u2014\s*(.+)$")
PART_HEAD = re.compile(r"^Part (\w+)\s*\u2014\s*(.+)$")
CLAUSE_HEAD = re.compile(r"^(\d+[A-Z]*(?:\.\d+[A-Z]*)?)\s+(.+)$")
COMPILATION_NO = re.compile(r"^Compilation No\.\s*(\d+)\s*$")
COMPILATION_DATE = re.compile(r"^Compilation date:\s*(\d{1,2} \w+ \d{4})\s*$")


# --------------------------------------------------------------------------
# Reading the Word file
# --------------------------------------------------------------------------


@dataclass
class Block:
    """One top-level item of the document body, in reading order."""

    kind: str                 # "p" or "table"
    style: str = ""
    text: str = ""
    rows: list[list[str]] = field(default_factory=list)


def _clean(text: str) -> str:
    return text.replace("\u00a0", " ")


def _run_text(element) -> str:
    out = []
    for el in element.iter():
        if el.tag == W + "t":
            out.append(el.text or "")
        elif el.tag == W + "tab":
            out.append("\t")
        elif el.tag == W + "br":
            out.append(" ")
        elif el.tag == W + "noBreakHyphen":
            out.append("-")
    return _clean("".join(out))


def _style(paragraph) -> str:
    node = paragraph.find(f"{W}pPr/{W}pStyle")
    return node.get(W + "val") if node is not None else ""


def _table_rows(table) -> list[list[str]]:
    rows = []
    for tr in table.findall(W + "tr"):
        row = []
        for tc in tr.findall(W + "tc"):
            parts = [_run_text(p).strip() for p in tc.findall(W + "p")]
            row.append(" ".join(part for part in parts if part))
            span = tc.find(f"{W}tcPr/{W}gridSpan")
            if span is not None:
                row.extend([""] * (int(span.get(W + "val")) - 1))
        rows.append(row)
    return rows


def read_blocks(docx: Path) -> list[Block]:
    with zipfile.ZipFile(docx) as archive:
        root = ET.fromstring(archive.read("word/document.xml"))
    body = root.find(W + "body")
    blocks = []
    for child in body:
        if child.tag == W + "p":
            blocks.append(Block("p", _style(child), _run_text(child)))
        elif child.tag == W + "tbl":
            blocks.append(Block("table", rows=_table_rows(child)))
    return blocks


def read_compilation(blocks: list[Block]) -> tuple[int, str]:
    """Compilation number and ISO date, from the cover page."""
    number = date = None
    for block in blocks:
        text = block.text.strip()
        if number is None and (m := COMPILATION_NO.match(text)):
            number = int(m.group(1))
        if date is None and (m := COMPILATION_DATE.match(text)):
            date = datetime.strptime(m.group(1), "%d %B %Y").date().isoformat()
        if number is not None and date is not None:
            return number, date
    raise ValueError("no compilation number and date on the cover page")


# --------------------------------------------------------------------------
# Splitting into clauses
# --------------------------------------------------------------------------


@dataclass
class Clause:
    schedule: str
    schedule_title: str
    part: str
    part_title: str
    group: str
    number: str
    heading: str
    blocks: list[Block] = field(default_factory=list)

    @property
    def id(self) -> str:
        return f"{SCHEDULES[self.schedule]}-{self.number}"

    @property
    def citation(self) -> str:
        return f"{INSTRUMENT} Schedule {self.schedule} clause {self.number}"

    @property
    def empty(self) -> bool:
        return not any(b.kind == "table" or b.text.strip() for b in self.blocks)


def split(blocks: list[Block]) -> list[Clause]:
    """Clauses of Schedules 1, 2 and 2A, in document order.

    Refuses to return anything if a wanted Schedule is missing, because a
    silently short corpus looks exactly like a complete one.
    """
    clauses: list[Clause] = []
    found: set[str] = set()
    schedule = schedule_title = part = part_title = ""
    current: Clause | None = None

    for block in blocks:
        if block.kind == "p" and block.style == "ActHead1":
            m = SCHEDULE_HEAD.match(block.text.strip())
            schedule, schedule_title = (m.group(1), m.group(2).strip()) if m else ("", "")
            part = part_title = ""
            current = None
            if schedule in SCHEDULES:
                found.add(schedule)
            continue
        if schedule not in SCHEDULES:
            continue
        if block.kind == "p" and block.style == "ActHead2":
            m = PART_HEAD.match(block.text.strip())
            if m:
                part, part_title = m.group(1), m.group(2).strip()
            current = None
            continue
        if block.kind == "p" and block.style == "ActHead5":
            m = CLAUSE_HEAD.match(block.text.strip())
            if not m:
                raise ValueError(f"unreadable clause heading: {block.text!r}")
            current = Clause(schedule, schedule_title, part, part_title, "",
                             m.group(1), m.group(2).strip())
            clauses.append(current)
            continue
        if current is not None and block.style != "Header":
            current.blocks.append(block)

    missing = [s for s in SCHEDULES if s not in found]
    if missing:
        raise ValueError(f"Schedules not found in the source: {', '.join(missing)}")
    return _fold_groups(clauses)


def _fold_groups(clauses: list[Clause]) -> list[Clause]:
    """Drop empty group headings and record them on the clauses beneath."""
    out = []
    group: Clause | None = None
    for index, clause in enumerate(clauses):
        after = clauses[index + 1] if index + 1 < len(clauses) else None
        if (
            clause.empty
            and after is not None
            and after.schedule == clause.schedule
            and after.number.startswith(clause.number + ".")
        ):
            group = clause
            continue
        if (
            group is not None
            and group.schedule == clause.schedule
            and clause.number.startswith(group.number + ".")
        ):
            clause.group = f"{group.number} {group.heading}"
        else:
            group = None
        out.append(clause)
    return out


# --------------------------------------------------------------------------
# Rendering
# --------------------------------------------------------------------------

LIST_DEPTH = {"paragraph": 0, "paragraphsub": 1, "paragraphsub-sub": 2, "notepara": 0}
NOTES = {"notetext", "notemargin", "notepara"}
LABEL = re.compile(r"^\([0-9a-zA-Z]+\)")


def _label_and_text(text: str) -> str:
    """'\\t(a)\\ttext' becomes '(a) text'. Tabs are layout, not content."""
    return re.sub(r"\s*\t\s*", " ", text).strip()


def _table(rows: list[list[str]]) -> list[str]:
    width = max(len(r) for r in rows)
    rows = [[c.replace("|", "\\|") for c in r] + [""] * (width - len(r)) for r in rows]
    lines = ["| " + " | ".join(rows[0]) + " |", "|" + "---|" * width]
    lines += ["| " + " | ".join(r) + " |" for r in rows[1:]]
    return lines


def render_body(blocks: list[Block]) -> str:
    """Markdown for a clause body.

    A labelled paragraph, (a) or (i), is a list item indented by its depth.
    An unlabelled paragraph is the closing words of the list above it and
    stands on its own, so it is never read as part of the last item. A note's
    own paragraphs stay inside the note's quote.
    """
    out: list[str] = []
    previous = ""          # "list", "note" or ""
    for block in blocks:
        if block.kind == "table":
            out += ["", *_table(block.rows)]
            previous = ""
            continue
        text = _label_and_text(block.text)
        if not text:
            continue
        if block.style == "notepara":
            if previous != "note":
                out.append("")
            out.append(f"> - {text}")
            previous = "note"
            continue
        if block.style in LIST_DEPTH and LABEL.match(text):
            indent = "  " * LIST_DEPTH[block.style]
            if previous != "list":
                out.append("")
            out.append(f"{indent}- {text}")
            previous = "list"
            continue
        if block.style in NOTES:
            out += ["", f"> {text}"]
            previous = "note"
            continue
        line = f"*{text}*" if block.style == "SubsectionHead" else text
        out += ["", line]
        previous = ""
    return "\n".join(out).strip() + "\n"


def render(clause: Clause, compilation: int, compilation_date: str) -> str:
    meta = {
        "id": clause.id,
        "instrument": INSTRUMENT,
        "register_id": REGISTER_ID,
        "compilation": compilation,
        "compilation_date": compilation_date,
        "schedule": clause.schedule,
        "schedule_title": clause.schedule_title,
        "part": clause.part,
        "part_title": clause.part_title,
        "group": clause.group,
        "clause": clause.number,
        "heading": clause.heading,
        "citation": clause.citation,
    }
    front = "\n".join(f"{key}: {value}" for key, value in meta.items())
    title = f"# Schedule {clause.schedule} clause {clause.number} {clause.heading}"
    return f"---\n{front}\n---\n\n{title}\n\n{render_body(clause.blocks)}"


# --------------------------------------------------------------------------
# Writing
# --------------------------------------------------------------------------


def clause_files(out_dir: Path) -> list[Path]:
    """Files this script owns. Nothing else in the folder is touched."""
    return sorted(
        path
        for prefix in SCHEDULES.values()
        for path in out_dir.glob(f"{prefix}-*.md")
    )


def write(source: Path, out_dir: Path) -> tuple[int, str, dict[str, int]]:
    blocks = read_blocks(source)
    compilation, compilation_date = read_compilation(blocks)
    clauses = split(blocks)

    ids = [c.id for c in clauses]
    duplicates = sorted({i for i in ids if ids.count(i) > 1})
    if duplicates:
        raise ValueError(f"duplicate clause ids: {', '.join(duplicates)}")

    out_dir.mkdir(parents=True, exist_ok=True)
    # Stale files from an older compilation would otherwise survive a
    # renumbering and be cited as if current.
    for path in clause_files(out_dir):
        path.unlink()
    for clause in clauses:
        (out_dir / f"{clause.id}.md").write_text(
            render(clause, compilation, compilation_date), encoding="utf-8"
        )

    counts = {s: sum(1 for c in clauses if c.schedule == s) for s in SCHEDULES}
    return compilation, compilation_date, counts


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Split the Regulations into clause files.")
    parser.add_argument("--source", type=Path, default=SOURCE)
    parser.add_argument("--out", type=Path, default=OUT_DIR)
    args = parser.parse_args(argv)

    if not args.source.exists():
        print(f"source not found: {args.source}", file=sys.stderr)
        print("Download the Word version from "
              f"https://www.legislation.gov.au/{REGISTER_ID}/latest/downloads",
              file=sys.stderr)
        return 1

    compilation, compilation_date, counts = write(args.source, args.out)
    summary = ", ".join(f"Schedule {s}: {n}" for s, n in counts.items())
    print(f"Compilation {compilation} ({compilation_date}). {summary}. "
          f"{sum(counts.values())} clause files written to {args.out}")
    if compilation != CHECKED_COMPILATION:
        print(f"WARNING: the rules were checked against compilation "
              f"{CHECKED_COMPILATION}, not {compilation}. Recheck them against "
              "this text before trusting a result.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
