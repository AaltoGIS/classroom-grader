import zipfile

import pytest
from openpyxl import Workbook, load_workbook
from openpyxl.comments import Comment
from openpyxl.styles import PatternFill
from openpyxl.worksheet.formula import ArrayFormula

from classroom_grader import cli

ROSTER = (
    "user,role,grader\n"
    "alice,student,Emma\nemma-v,ta,\nbob,student,\ncarol,student,Aliisa\n"
    "dave,student,=1+1\n"
)
SETTINGS = 'organization = "IntroSDA-2026"\nroster = "student_info.csv"\n'
FILL = "FFFFF2CC"


@pytest.fixture
def template(tmp_path):
    """A grading template: headers, an example row and a pass limit in row 7."""
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Grading"
    sheet.append(["user", "Lastname", "Examiner", "Ex1", "Ex2", "Total", "Pass"])
    sheet.append(["me", "=Me", '="TA Smith"', 10, 9, "=SUM(D2:E2)", None])
    sheet["A2"].hyperlink = "https://github.com/me"
    sheet["G2"] = ArrayFormula("G2", "=IF(F2>=B$7,1,0)")
    sheet["B2"].data_type = "s"  # text that looks like a formula
    sheet["C2"].fill = PatternFill("solid", fgColor=FILL)
    sheet.row_dimensions[2].height = 30
    sheet.row_dimensions[4].hidden = True
    sheet["A7"], sheet["B7"] = "Pass limit", 15
    workbook.create_sheet("Notes")["A1"] = "Kept as it is"
    path = tmp_path / "template.xlsx"
    workbook.save(path)
    return path


def test_every_student_gets_the_example_rows_formulas(course, template, capsys):
    (course / "student_info.csv").write_text(ROSTER, encoding="utf-8")
    (course / "grader.toml").write_text(SETTINGS, encoding="utf-8")
    output = course / "grading.xlsx"
    args = ["--template", str(template), "--output", str(output)]
    assert cli.main(["grading-sheet", *args, "--course", str(course)]) == 0
    assert capsys.readouterr().out == f"Wrote {output}: 4 students\n"

    workbook = load_workbook(output)
    sheet = workbook["Grading"]
    rows = sheet.iter_rows(min_row=2, max_row=6, max_col=6, values_only=True)
    assert list(rows) == [
        ("alice", None, "Emma", None, None, "=SUM(D2:E2)"),
        ("bob", None, None, None, None, "=SUM(D3:E3)"),
        ("carol", None, "Aliisa", None, None, "=SUM(D4:E4)"),
        ("dave", None, "=1+1", None, None, "=SUM(D5:E5)"),
        (None, None, None, None, None, None),
    ]
    assert sheet["C5"].data_type == "s"
    assert sheet["A2"].hyperlink is None
    passed = sheet["G4"].value
    assert (passed.ref, passed.text) == ("G4", "=IF(F4>=B$7,1,0)")
    assert sheet["C4"].fill.fgColor.rgb == FILL
    assert sheet.row_dimensions[4].height == 30
    assert not sheet.row_dimensions[4].hidden
    assert (sheet["A7"].value, sheet["B7"].value) == ("Pass limit", 15)
    assert workbook["Notes"]["A1"].value == "Kept as it is"


@pytest.mark.parametrize(
    ("roster", "case", "message"),
    [
        (
            "user\n" + "".join(f"s{n}\n" for n in range(6)),
            "",
            "Grading!A7 is not empty, but the 6 students need rows 2-7",
        ),
        ("user\n", "", "the roster has no students"),
        ("user\nalice\n", "output exists", "grading.xlsx exists already"),
        ("user\nalice\n", "no username column", "no sheet has a username column"),
        ("user\nalice\nbob\n", "merged", "Grading!A3:B3 is merged"),
        ("user\nalice\nbob\n", "comment", "Grading!B3 is not empty"),
        ("user\nalice\n", "damaged", "is not an Excel workbook"),
        ("user\nalice\n", "array over rows", "Grading!G2: an array formula over"),
        ("user\nalice\n", "unreadable formula", "Grading!F2: the formula cannot be"),
    ],
)
def test_refusals_write_nothing(tmp_path, template, capsys, roster, case, message):
    roster_path = tmp_path / "roster.csv"
    roster_path.write_text(roster, encoding="utf-8")
    output = tmp_path / "grading.xlsx"
    if case == "output exists":
        output.write_bytes(b"old")
    if case in (
        "no username column",
        "merged",
        "comment",
        "array over rows",
        "unreadable formula",
    ):
        workbook = load_workbook(template)
        sheet = workbook["Grading"]
        if case == "no username column":
            sheet["A1"] = "student"
        if case == "merged":
            sheet.merge_cells("A3:B3")
        if case == "comment":
            sheet["B3"].comment = Comment("Old note", "Teacher")
        if case == "array over rows":
            sheet["G2"] = ArrayFormula("G2:G3", "=F2:F3*2")
        if case == "unreadable formula":
            sheet["F2"] = "=D2#"
        workbook.save(template)
    if case == "damaged":
        template = tmp_path / "damaged.xlsx"
        with zipfile.ZipFile(template, "w") as archive:
            archive.writestr("[Content_Types].xml", "<unclosed")
    args = ["--template", str(template), "--output", str(output)]
    assert cli.main(["grading-sheet", *args, "--roster", str(roster_path)]) == 1
    assert message in capsys.readouterr().err
    assert (
        output.read_bytes() == b"old"
        if case == "output exists"
        else not output.exists()
    )
