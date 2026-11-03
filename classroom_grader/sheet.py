"""``grader grading-sheet``: a grading spreadsheet with one row per roster student."""

import argparse
import io
from collections import Counter
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill
from openpyxl.utils.cell import get_column_letter
from openpyxl.worksheet.worksheet import Worksheet

from classroom_grader import GraderError, replace_file, write_new
from classroom_grader.course import add_course_option, course_settings, load_roster
from classroom_grader.roster import Student, roster_with_graders, split_between
from classroom_grader.settings import (
    GRADES,
    LIMITS_SHEET,
    SETTINGS_FILE,
    SHEET_FIRST_COLUMNS,
    SHEET_LAST_COLUMNS,
    SHEET_MIDDLE_COLUMNS,
    GradingSheet,
)

HELP = "Write the grading spreadsheet from grader.toml, one row per student."
EXAMINER_COLUMN = SHEET_FIRST_COLUMNS.index("Examiner") + 1
COLUMN_WIDTHS = {
    "user": 32,
    "Lastname": 32,
    "Firstname": 27,
    "Examiner": 22,
    SHEET_FIRST_COLUMNS[-1]: 64,
}
MIN_COLUMN_WIDTH = 9
TOTAL_FILL = PatternFill("solid", fgColor="FFD0E0E3")
GRADE_FILL = PatternFill("solid", fgColor="FFD9EAD3")
GRADE_FONT = Font(size=13, bold=True)
# Rows of the limits sheet that the students' formulas read.
SCALING_ROW = 4
TOTAL_MAX_ROW = 5
BEST_GRADE_ROW = 6


def add_arguments(parser: argparse.ArgumentParser) -> None:
    """Add the ``grader grading-sheet`` options."""
    parser.add_argument(
        "--output", type=Path, required=True, help="workbook to write; must not exist"
    )
    parser.add_argument(
        "--assistant",
        action="append",
        metavar="NAME",
        help="split the students between these graders, also in the roster's "
        "grader column; repeat for each",
    )
    add_course_option(parser)


def run(args: argparse.Namespace) -> int:
    """Write the spreadsheet of ``[grading_sheet]`` to ``--output``.

    With ``--assistant``, the students are first split into blocks between the
    assistants, and the split is also written into the roster.
    """
    settings = course_settings(args)
    if settings.grading_sheet is None:
        raise GraderError(
            f"{settings.root / SETTINGS_FILE} has no [grading_sheet] table; add one "
            'as in "The grading spreadsheet" in docs/setting-up-a-course.md'
        )
    roster_path, username_column = settings.roster, settings.username_column
    students = load_roster(roster_path, username_column).students
    if not students:
        raise GraderError("the roster has no students")
    assistants = _assistant_names(args.assistant or [])
    new_roster = None
    if assistants:
        if any(student.grader for student in students):
            raise GraderError(
                f"{roster_path} names graders already; leave out --assistant to "
                "use them, or empty its grader column first"
            )
        students = split_between(students, assistants)
        graders = {student.username.casefold(): student.grader for student in students}
        new_roster = roster_with_graders(roster_path, graders, username_column)
    content = io.BytesIO()
    grading_workbook(settings.grading_sheet, students).save(content)
    write_new(args.output, content.getvalue())
    if new_roster is not None:
        try:
            replace_file(roster_path, new_roster)
        except OSError:
            args.output.unlink(missing_ok=True)
            raise
    count = len(students)
    print(f"Wrote {args.output}: {count} student{'' if count == 1 else 's'}")
    if assistants:
        counts = Counter(student.grader for student in students)
        split = ", ".join(f"{name} {counts[name]}" for name in assistants)
        print(f"Wrote the graders into {roster_path}: {split}")
    return 0


def _assistant_names(names: list[str]) -> list[str]:
    """Return the ``--assistant`` names stripped; refuse blank or repeated ones."""
    names = [name.strip() for name in names]
    if not all(names) or len({name.casefold() for name in names}) < len(names):
        raise GraderError("--assistant needs a different, non-empty name each time")
    return names


def grading_workbook(spec: GradingSheet, students: list[Student]) -> Workbook:
    """Return a workbook with a sheet of the students and a sheet of the limits.

    The students take a row each, in roster order, with empty points and
    formulas for the totals and the grade. The limits have a sheet of their own,
    so that sorting the students cannot move them.
    """
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = spec.name
    _write_limits(workbook.create_sheet(LIMITS_SHEET), spec)
    columns = [
        *SHEET_FIRST_COLUMNS,
        *spec.exercises,
        *SHEET_MIDDLE_COLUMNS,
        *spec.quizzes,
        *SHEET_LAST_COLUMNS,
    ]
    for number, name in enumerate(columns, start=1):
        cell = sheet.cell(1, number, name)
        cell.data_type = "s"  # a column name starting with "=" stays text
        width = COLUMN_WIDTHS.get(name, max(len(name) + 2, MIN_COLUMN_WIDTH))
        sheet.column_dimensions[get_column_letter(number)].width = width
    first_exercise = len(SHEET_FIRST_COLUMNS) + 1
    last_exercise = len(SHEET_FIRST_COLUMNS) + len(spec.exercises)
    exercises_total = last_exercise + 2
    first_quiz = exercises_total + 1
    last_quiz = exercises_total + len(spec.quizzes)
    quizzes_total = last_quiz + 1
    quiz_points, extra_points, total, grade = (quizzes_total + n for n in (1, 2, 3, 4))
    sheet.cell(1, grade).fill = GRADE_FILL
    for row, student in enumerate(students, start=2):
        sheet.cell(row, 1, student.username)
        if student.grader is not None:
            cell = sheet.cell(row, EXAMINER_COLUMN, student.grader)
            cell.data_type = "s"  # a name starting with "=" stays text
        sheet.cell(
            row,
            exercises_total,
            f"=SUM({_cell_name(first_exercise, row)}:{_cell_name(last_exercise, row)})",
        )
        sheet.cell(
            row,
            quizzes_total,
            f"=SUM({_cell_name(first_quiz, row)}:{_cell_name(last_quiz, row)})",
        )
        sheet.cell(
            row,
            quiz_points,
            f"={_cell_name(quizzes_total, row)}*{LIMITS_SHEET}!B${SCALING_ROW}",
        )
        points = [
            _cell_name(c, row) for c in (exercises_total, quiz_points, extra_points)
        ]
        sheet.cell(row, total, f"={'+'.join(points)}").fill = TOTAL_FILL
        cell = sheet.cell(row, grade, _grade_formula(_cell_name(total, row)))
        cell.fill, cell.font = GRADE_FILL, GRADE_FONT
    sheet.freeze_panes = sheet.cell(2, len(SHEET_FIRST_COLUMNS))
    last = f"{get_column_letter(len(columns))}{len(students) + 1}"
    sheet.auto_filter.ref = f"A1:{last}"
    return workbook


def _cell_name(column: int, row: int) -> str:
    """Return the name of a cell, such as ``F2``."""
    return f"{get_column_letter(column)}{row}"


def _grade_formula(total: str) -> str:
    """Return the grade of the points in cell ``total``, from the limits sheet.

    Nested IF, because Excel keeps IFS in its files under another name.
    """
    formula = "0"
    for grade in range(1, GRADES + 1):
        row = BEST_GRADE_ROW + GRADES - grade
        formula = f"IF({total}>={LIMITS_SHEET}!B${row},{grade},{formula})"
    return f"={formula}"


def _write_limits(sheet: Worksheet, spec: GradingSheet) -> None:
    """Fill the limits sheet; a later change to a value there reaches every grade."""
    exercise_points = "+".join(str(points) for points in spec.exercises.values())
    rows = [
        ("Quiz max points", spec.quiz_max_points),
        ("Minimum quiz points for pass", f"=B1*{spec.quiz_pass_share}"),
        ("Exercises max points", f"={exercise_points}"),
        ("Quiz to exercises scaling ratio", "=B3/B1"),
        ("Total max points (scaled)", "=B3+B1*B4"),
    ]
    rows += [
        (f"Grade {grade} min points", f"=B{TOTAL_MAX_ROW}*{share}")
        for grade, share in zip(range(GRADES, 0, -1), spec.grade_limits, strict=True)
    ]
    for row in rows:
        sheet.append(row)
    sheet.column_dimensions["A"].width = 32
