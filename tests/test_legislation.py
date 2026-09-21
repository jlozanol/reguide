"""Tests for the clause splitter and the corpus reader.

Two groups. The first builds tiny Word files in a temporary folder, so it runs
everywhere and pins the parsing rules. The second runs the splitter on the
real Regulations and checks the result against the document; it is skipped
when data/legislation/source/ does not hold the file, which is the case on a
fresh clone because the source is gitignored.

Nothing here reads the clause files already in data/legislation/. The real
source is split into a temporary folder every run, so a stale corpus can
never make these tests pass.
"""

import importlib.util
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

import pytest

from reguide import legislation as LEG

ROOT = Path(__file__).resolve().parent.parent
SPEC = importlib.util.spec_from_file_location(
    "load_legislation", ROOT / "scripts" / "load_legislation.py"
)
L = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(L)

REAL_SOURCE = L.SOURCE
needs_source = pytest.mark.skipif(
    not REAL_SOURCE.exists(),
    reason=f"legislation source not downloaded: {REAL_SOURCE.name}",
)

EM = "\u2014"
NBSP = "\u00a0"


# --------------------------------------------------------------------------
# Synthetic documents
# --------------------------------------------------------------------------

NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


def para(style: str, text: str) -> str:
    runs = []
    for i, piece in enumerate(text.split("\t")):
        if i:
            runs.append("<w:r><w:tab/></w:r>")
        if piece:
            runs.append(f'<w:r><w:t xml:space="preserve">{escape(piece)}</w:t></w:r>')
    ppr = f'<w:pPr><w:pStyle w:val="{style}"/></w:pPr>' if style else ""
    return f"<w:p>{ppr}{''.join(runs)}</w:p>"


def table(rows: list[list[str]]) -> str:
    body = "".join(
        "<w:tr>" + "".join(f"<w:tc>{para('Tabletext', c)}</w:tc>" for c in row) + "</w:tr>"
        for row in rows
    )
    return f"<w:tbl>{body}</w:tbl>"


def make_docx(path: Path, body: list[str]) -> Path:
    xml = (f'<?xml version="1.0" encoding="UTF-8"?><w:document xmlns:w="{NS}">'
           f"<w:body>{''.join(body)}</w:body></w:document>")
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("word/document.xml", xml)
    return path


COVER = [
    para("ShortT", "Therapeutic Goods (Medical Devices) Regulations 2002"),
    para("", "Compilation No. 72"),
    para("", "Compilation date:\t8 September 2026"),
]


def minimal(extra_s1=(), extra_s2a=()) -> list[str]:
    return COVER + [
        para("ActHead5", "3.1  A regulation outside every Schedule"),
        para("subsection", "\t\tNot a clause of any wanted Schedule."),
        para("ActHead1", f"Schedule{NBSP}1{EM}Essential principles"),
        para("ActHead2", f"Part 2{EM}Other principles"),
        para("ActHead5", "7  Chemical, physical and biological properties"),
        para("ActHead5", "7.1  Choice of materials"),
        para("subsection", "\t(1)\tMaterials must be chosen with regard to toxicity."),
        para("ActHead5", "7.2  Contaminants"),
        para("subsection", "\t\tRisks from contaminants must be minimised."),
        para("ActHead5", "10  Measuring function"),
        para("subsection", "\t\tA measuring device must be accurate."),
        *extra_s1,
        para("ActHead1", f"Schedule{NBSP}2{EM}Classification rules for medical devices"),
        para("ActHead2", f"Part 5{EM}Special rules"),
        para("ActHead5", " 5.8  Medical devices intended for export only"),
        para("subsection", "\t\tA device for export only is Class I."),
        para("ActHead1", f"Schedule{NBSP}2A{EM}Classification rules for IVD medical devices"),
        para("notemargin", "Note:\tRegulation 3.2 provides for the classification rules."),
        para("Header", "  "),
        para("ActHead5", "1.6  Reagents, instruments etc"),
        para("subsection", "\t(2)\tThe following are Class 1:"),
        para("paragraph", "\t(a)\tan instrument;"),
        para("paragraph", "\t(b)\ta microbiological culture medium."),
        para("notetext", "Note:\tA note."),
        para("notepara", "(a)\tfirst; or"),
        *extra_s2a,
        para("ActHead1", f"Schedule{NBSP}3{EM}Conformity assessment procedures"),
        para("ActHead5", "1.1  Not wanted"),
        para("subsection", "\t\tOutside the wanted Schedules."),
    ]


@pytest.fixture
def synthetic(tmp_path):
    return make_docx(tmp_path / "regs.docx", minimal())


def test_compilation_is_read_from_the_cover(synthetic):
    assert L.read_compilation(L.read_blocks(synthetic)) == (72, "2026-09-08")


def test_a_cover_without_a_compilation_is_refused(tmp_path):
    path = make_docx(tmp_path / "bare.docx", minimal()[3:])
    with pytest.raises(ValueError, match="compilation"):
        L.read_compilation(L.read_blocks(path))


def test_only_the_three_schedules_are_split(synthetic):
    ids = [c.id for c in L.split(L.read_blocks(synthetic))]
    assert ids == ["s1-7.1", "s1-7.2", "s1-10", "s2-5.8", "s2a-1.6"]


def test_a_missing_schedule_is_refused_not_skipped(tmp_path):
    body = [b for b in minimal() if "Schedule\u00a02A" not in b]
    path = make_docx(tmp_path / "short.docx", body)
    with pytest.raises(ValueError, match="2A"):
        L.split(L.read_blocks(path))


def test_group_headings_are_folded_into_their_clauses(synthetic):
    clauses = {c.id: c for c in L.split(L.read_blocks(synthetic))}
    assert "s1-7" not in clauses
    assert clauses["s1-7.1"].group == "7 Chemical, physical and biological properties"
    assert clauses["s1-7.2"].group == clauses["s1-7.1"].group
    assert clauses["s1-10"].group == ""


def test_headings_are_trimmed_and_parts_recorded(synthetic):
    clauses = {c.id: c for c in L.split(L.read_blocks(synthetic))}
    export = clauses["s2-5.8"]
    assert (export.number, export.heading) == ("5.8", "Medical devices intended for export only")
    assert (export.part, export.part_title) == ("5", "Special rules")
    assert clauses["s1-7.1"].schedule_title == "Essential principles"


def test_running_headers_and_schedule_notes_are_left_out(synthetic):
    clause = {c.id: c for c in L.split(L.read_blocks(synthetic))}["s2a-1.6"]
    text = L.render_body(clause.blocks)
    assert "Regulation 3.2" not in text
    assert text.startswith("(2) The following are Class 1:")


def test_render_keeps_structure(synthetic):
    clause = {c.id: c for c in L.split(L.read_blocks(synthetic))}["s2a-1.6"]
    page = L.render(clause, 72, "2026-09-08")
    assert "id: s2a-1.6\n" in page
    assert ("citation: Therapeutic Goods (Medical Devices) Regulations 2002 "
            "Schedule 2A clause 1.6\n") in page
    assert "# Schedule 2A clause 1.6 Reagents, instruments etc" in page
    assert "\n- (a) an instrument;\n- (b) a micro" in page
    assert "> Note: A note.\n> - (a) first; or" in page


def test_closing_words_are_not_read_as_a_list_item(tmp_path):
    extra = [
        para("ActHead5", "13A.2  Patient implant cards"),
        para("subsection", "\t(1)\tEither:"),
        para("paragraph", "\t(a)\ta card; or"),
        para("paragraph", "\t\tmust be made available."),
    ]
    path = make_docx(tmp_path / "closing.docx", minimal(extra_s1=extra))
    clause = {c.id: c for c in L.split(L.read_blocks(path))}["s1-13A.2"]
    assert L.render_body(clause.blocks).endswith("- (a) a card; or\n\nmust be made available.\n")


def test_tables_become_markdown(tmp_path):
    extra = [table([["Item", "Information"], ["1", "The name | model"]])]
    path = make_docx(tmp_path / "table.docx", minimal(extra_s1=extra))
    clause = {c.id: c for c in L.split(L.read_blocks(path))}["s1-10"]
    body = L.render_body(clause.blocks)
    assert "| Item | Information |\n|---|---|\n| 1 | The name \\| model |" in body


def test_write_replaces_stale_files_and_leaves_others(synthetic, tmp_path):
    out = tmp_path / "out"
    out.mkdir()
    (out / "s2-9.9.md").write_text("from an older compilation")
    (out / "excluded_goods_determination_2018.json").write_text("{}")
    compilation, date, counts = L.write(synthetic, out)
    assert (compilation, date) == (72, "2026-09-08")
    assert counts == {"1": 3, "2": 1, "2A": 1}
    assert not (out / "s2-9.9.md").exists()
    assert (out / "excluded_goods_determination_2018.json").exists()
    assert sorted(p.name for p in L.clause_files(out)) == [
        "s1-10.md", "s1-7.1.md", "s1-7.2.md", "s2-5.8.md", "s2a-1.6.md",
    ]


def test_main_reports_a_missing_source(tmp_path, capsys):
    assert L.main(["--source", str(tmp_path / "absent.docx"), "--out", str(tmp_path)]) == 1
    assert "legislation.gov.au/F2002B00237" in capsys.readouterr().err


def test_main_warns_on_an_unchecked_compilation(tmp_path, capsys):
    body = minimal()
    body[1] = para("", "Compilation No. 73")
    path = make_docx(tmp_path / "newer.docx", body)
    assert L.main(["--source", str(path), "--out", str(tmp_path / "out")]) == 0
    assert "checked against compilation 72, not 73" in capsys.readouterr().err


# --------------------------------------------------------------------------
# The reader
# --------------------------------------------------------------------------


def test_reader_round_trips_what_the_splitter_writes(synthetic, tmp_path):
    L.write(synthetic, tmp_path)
    clauses = LEG.load(tmp_path)
    clause = clauses["s2a-1.6"]
    assert clause.schedule == "2A"
    assert clause.clause == "1.6"
    assert clause.compilation == 72
    assert clause.citation.endswith("Schedule 2A clause 1.6")
    assert clause.text.startswith("# Schedule 2A clause 1.6")


def test_an_empty_corpus_is_reported_not_treated_as_no_match(tmp_path):
    with pytest.raises(LEG.CorpusMissing):
        LEG.load(tmp_path)


def test_find_needs_every_keyword_and_ignores_case(synthetic, tmp_path):
    L.write(synthetic, tmp_path)
    clauses = LEG.load(tmp_path)
    assert [c.id for c in LEG.find(clauses, "EXPORT only")] == ["s2-5.8"]
    assert LEG.find(clauses, "export", "instrument") == []
    assert LEG.find(clauses) == []


# --------------------------------------------------------------------------
# The real Regulations
# --------------------------------------------------------------------------


@pytest.fixture(scope="module")
def real(tmp_path_factory):
    out = tmp_path_factory.mktemp("legislation")
    compilation, date, counts = L.write(REAL_SOURCE, out)
    return {"compilation": compilation, "date": date, "counts": counts,
            "clauses": LEG.load(out)}


@needs_source
def test_real_source_is_the_compilation_the_rules_were_checked_against(real):
    assert real["compilation"] == L.CHECKED_COMPILATION, (
        "a new compilation: recheck every rule against its text, then update "
        "CHECKED_COMPILATION"
    )
    assert real["date"] == "2026-09-08"


@needs_source
def test_real_clause_counts(real):
    assert real["counts"] == {"1": 57, "2": 29, "2A": 8}


@needs_source
def test_real_schedule_2a_is_complete(real):
    ids = sorted(i for i in real["clauses"] if i.startswith("s2a-"))
    assert ids == [f"s2a-1.{n}" for n in range(1, 9)]


@needs_source
@pytest.mark.parametrize("clause_id", [
    "s2-1.1", "s2-2.2A", "s2-2.4", "s2-3.4", "s2-4.3", "s2-4.5", "s2-4.6",
    "s2-4.7", "s2-5.1", "s2-5.4", "s2-5.11",
])
def test_real_schedule_2_rules_the_fixtures_cite_exist(real, clause_id):
    assert clause_id in real["clauses"]


@needs_source
def test_real_schedule_1_groups_are_folded(real):
    clauses = real["clauses"]
    for group in ["7", "8", "9", "11", "12", "13", "13A", "13C"]:
        assert f"s1-{group}" not in clauses
    assert clauses["s1-12.1"].path.read_text().count(
        "group: 12 Medical devices connected to or equipped with an energy source") == 1
    for standalone in ["1", "6", "10", "13B", "14", "15"]:
        assert f"s1-{standalone}" in clauses


@needs_source
def test_real_clause_text_is_verbatim(real):
    clauses = real["clauses"]
    assert "Despite clauses 1.1 to 1.5" in clauses["s2a-1.6"].text
    assert "- (c) a microbiological culture medium." in clauses["s2a-1.6"].text
    assert "non assay-specific quality control material" in clauses["s2a-1.5"].text
    assert "Despite clauses 1.1 to 1.7" in clauses["s2a-1.8"].text
    assert clauses["s2-4.6"].heading.startswith("Programmed or programmable")
    assert "Class IIb; or" in clauses["s2-4.6"].text


@needs_source
def test_real_paragraph_and_subparagraph_i_stay_distinct(real):
    text = real["clauses"]["s2a-1.3"].text
    assert "\n  - (i) for selective therapy and management; or" in text
    assert "\n- (i) the management of patients suffering" in text


@needs_source
def test_real_keyword_lookup_finds_the_named_exceptions(real):
    clauses = real["clauses"]
    assert LEG.find(clauses, "culture medium")[0].id == "s2a-1.6"
    assert LEG.find(clauses, "quality control material")[0].id == "s2a-1.5"
