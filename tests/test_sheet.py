import os

import pytest
from openpyxl import load_workbook

from classroom_grader import cli

ROSTER = (
    "user,role,grader\n"
    "alice,student,Emma\nemma-v,ta,\nbob,student,\ncarol,student,Alvina\n"
    "dave,student,=1+1\n"
)
SETTINGS = 'organization = "IntroSDA-2026"\nroster = "roster.csv"\n'
GRADING_SHEET = """
[grading_sheet]
name = "Teacher's grading"
exercises = { Ex1 = 20, Ex2 = 15 }
quizzes = ["Quiz1", "Quiz2"]
quiz_max_points = 100
quiz_pass_share = 0.4
grade_limits = [0.9, 0.8, 0.7, 0.6, 0.5]
"""
HEADERS = (
    "user",
    "Lastname",
    "Firstname",
    "Examiner",
    "Comments / Requires Checking?",
    "Ex1",
    "Ex2",
    "Feedback given",
    "Exercises Total",
    "Quiz1",
    "Quiz2",
    "Quizzes total",
    "Quiz points (scaled)",
    "Extra points (attendance)",
    "Total points",
    "Total grade",
)


def write_course(course, roster, settings=SETTINGS + GRADING_SHEET):
    """Write the course's settings and roster and return the roster's path."""
    (course / "grader.toml").write_text(settings, encoding="utf-8")
    path = course.resolve() / "roster.csv"
    path.write_bytes(roster)
    return path


def grading_sheet(course, *options):
    """Run ``grader grading-sheet`` in ``course``; return exit code and output path."""
    output = course / "grading.xlsx"
    args = ["--output", str(output), "--course", str(course), *options]
    return cli.main(["grading-sheet", *args]), output


def test_every_student_gets_a_row_with_formulas(course, capsys):
    write_course(course, ROSTER.encode())
    code, output = grading_sheet(course)
    assert code == 0
    assert capsys.readouterr().out == f"Wrote {output}: 4 students\n"

    workbook = load_workbook(output)
    assert workbook.sheetnames == ["Teacher's grading", "Limits"]
    sheet = workbook.active
    assert next(sheet.values) == HEADERS
    assert [row[:7] for row in sheet.iter_rows(min_row=2, values_only=True)] == [
        ("alice", None, None, "Emma", None, None, None),
        ("bob", None, None, None, None, None, None),
        ("carol", None, None, "Alvina", None, None, None),
        ("dave", None, None, "=1+1", None, None, None),
    ]
    assert sheet["D5"].data_type == "s"
    grade = "0"
    for points, row in zip(range(1, 6), range(10, 5, -1), strict=True):
        grade = f"IF(O3>=Limits!B${row},{points},{grade})"
    assert [sheet[f"{column}3"].value for column in "HIJKLMNOP"] == [
        None,
        "=SUM(F3:G3)",
        None,
        None,
        "=SUM(J3:K3)",
        "=L3*Limits!B$4",
        None,
        "=I3+M3+N3",
        f"={grade}",
    ]
    assert (sheet.freeze_panes, sheet.auto_filter.ref) == ("E2", "A1:P5")
    assert [value for _, value in workbook["Limits"].values] == [
        100,
        "=B1*0.4",
        "=20+15",
        "=B3/B1",
        "=B3+B1*B4",
        "=B5*0.9",
        "=B5*0.8",
        "=B5*0.7",
        "=B5*0.6",
        "=B5*0.5",
    ]


def test_left_out_thresholds_get_the_defaults(course):
    table = GRADING_SHEET.split("quiz_pass_share")[0]
    write_course(course, ROSTER.encode(), SETTINGS + table)
    _, output = grading_sheet(course)
    limits = [value for _, value in load_workbook(output)["Limits"].values]
    assert limits[1] == "=B1*0.5"
    assert limits[5:] == ["=B5*0.9", "=B5*0.8", "=B5*0.7", "=B5*0.6", "=B5*0.5"]


@pytest.mark.parametrize(
    ("roster", "settings", "message"),
    [
        (b"user\n", SETTINGS + GRADING_SHEET, "the roster has no students"),
        (b"user\nalice\n", SETTINGS + GRADING_SHEET, "grading.xlsx exists already"),
        (b"user\nalice\n", SETTINGS, "has no [grading_sheet] table"),
    ],
)
def test_refusals_leave_the_output_alone(course, capsys, roster, settings, message):
    write_course(course, roster, settings)
    output = course / "grading.xlsx"
    if "exists" in message:
        output.write_bytes(b"old")
    assert grading_sheet(course)[0] == 1
    assert message in capsys.readouterr().err
    assert output.read_bytes() == b"old" if "exists" in message else not output.exists()


@pytest.mark.parametrize(
    ("roster", "written"),
    [
        (
            '﻿username,role,"full\nname"\r\nteach,teacher,T\r\n'
            "s1,student,Väinö\r\ns2,student,\r\ns3,student,\r\ns4,student,\r\n"
            "s5,student,,extra\r\n",
            '﻿username,role,"full\nname",,grader\r\nteach,teacher,T\r\n'
            "s1,student,Väinö,,Emma\r\ns2,student,,,Emma\r\ns3,student,,,Emma\r\n"
            "s4,student,,,Alvina\r\ns5,student,,extra,Alvina\r\n",
        ),
        (
            "user;grader;role\ns1;;student\ns2;;\ns3;;student\ns1;Bob;student\n"
            "s4;;student\ns5;;student\ns2;;ta",
            "user;grader;role\ns1;Emma;student\ns2;Emma;\ns3;Emma;student\n"
            "s1;Bob;student\ns4;Alvina;student\ns5;Alvina;student\ns2;;ta",
        ),
        (
            'user,"full\nname"\rs1,"A\nB"\rs2,\rs3,\rs4,\rs5,\r',
            'user,"full\nname",grader\rs1,"A\nB",Emma\rs2,,Emma\rs3,,Emma\r'
            "s4,,Alvina\rs5,,Alvina\r",
        ),
    ],
)
def test_assistants_split_the_students_in_blocks(course, capsys, roster, written):
    roster_path = write_course(course, roster.encode())
    split = ["--assistant", "Emma", "--assistant", "Alvina"]
    code, output = grading_sheet(course, *split)
    assert code == 0
    assert capsys.readouterr().out == (
        f"Wrote {output}: 5 students\n"
        f"Wrote the graders into {roster_path}: Emma 3, Alvina 2\n"
    )
    sheet = load_workbook(output).active
    examiners = [sheet.cell(row, 4).value for row in range(2, 7)]
    assert examiners == ["Emma", "Emma", "Emma", "Alvina", "Alvina"]
    assert roster_path.read_bytes() == written.encode()


@pytest.mark.skipif(
    os.name == "nt", reason="symbolic links need extra rights on Windows"
)
def test_a_linked_roster_gets_the_graders_in_the_file_it_points_to(course, tmp_path):
    link = write_course(course, b"")
    link.unlink()
    target = tmp_path / "shared" / "roster.csv"
    target.parent.mkdir()
    target.write_bytes(b"user\nalice\n")
    link.symlink_to(target)
    assert grading_sheet(course, "--assistant", "Emma")[0] == 0
    assert link.is_symlink()
    assert target.read_bytes() == b"user,grader\nalice,Emma\n"


@pytest.mark.parametrize(
    ("roster", "assistants", "message"),
    [
        (b"user,grader\nalice,Emma\n", ["Alvina"], "roster.csv names graders already"),
        (b"user\nalice\n", ["Emma", " emma "], "a different, non-empty name each time"),
        ("user,name\nalice,Väinö\n".encode("cp1252"), ["日本"], "its encoding, cp1252"),
        (b"user\nalice\n", ["Emma"], "disk full"),
    ],
)
def test_assistant_refusals_change_nothing(
    course, capsys, monkeypatch, roster, assistants, message
):
    def full_disk(path, content):
        raise OSError("disk full")

    if message == "disk full":
        monkeypatch.setattr("classroom_grader.sheet.replace_file", full_disk)
    roster_path = write_course(course, roster)
    split = [option for name in assistants for option in ("--assistant", name)]
    assert grading_sheet(course, *split)[0] == 1
    assert message in capsys.readouterr().err
    assert roster_path.read_bytes() == roster
    assert not (course / "grading.xlsx").exists()
