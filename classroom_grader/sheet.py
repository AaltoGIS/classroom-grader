"""``grader grading-sheet``: a grading spreadsheet with one row per roster student."""

import argparse
import io
import zipfile
from collections import Counter
from copy import copy
from pathlib import Path

from openpyxl import Workbook, load_workbook
from openpyxl.cell.cell import Cell
from openpyxl.formula.tokenizer import TokenizerError
from openpyxl.formula.translate import Translator
from openpyxl.utils.cell import get_column_letter, range_boundaries
from openpyxl.utils.exceptions import InvalidFileException
from openpyxl.worksheet.formula import ArrayFormula, DataTableFormula
from openpyxl.worksheet.worksheet import Worksheet

from classroom_grader import GraderError, replace_file, write_new
from classroom_grader.course import add_course_option, course_settings, load_roster
from classroom_grader.roster import (
    GRADER_COLUMN,
    USERNAME_COLUMNS,
    Student,
    roster_with_graders,
    split_between,
)

HELP = "Write a grading spreadsheet from an Excel template, one row per student."
# The row under the headers whose formulas and formatting every student gets.
EXAMPLE_ROW = 2
# Headers of the column that gets each student's grader.
GRADER_HEADERS = (GRADER_COLUMN, "examiner")


def add_arguments(parser: argparse.ArgumentParser) -> None:
    """Add the ``grader grading-sheet`` options."""
    parser.add_argument(
        "--template",
        type=Path,
        required=True,
        help="Excel workbook (.xlsx) with headers in row 1 and an example row 2",
    )
    parser.add_argument(
        "--output", type=Path, required=True, help="workbook to write; must not exist"
    )
    parser.add_argument(
        "--roster",
        type=Path,
        help="roster CSV file (default: the roster in the course's grader.toml)",
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
    """Write the template filled with the roster's students to ``--output``.

    With ``--assistant``, the students are first split into blocks between the
    assistants, and the split is also written into the roster.
    """
    roster_path, username_column = args.roster, None
    if roster_path is None:
        settings = course_settings(args)
        roster_path, username_column = settings.roster, settings.username_column
    students = load_roster(roster_path, username_column).students
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
    workbook = fill_template(args.template, students, needs_graders=bool(assistants))
    content = io.BytesIO()
    workbook.save(content)
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


def fill_template(
    template: Path, students: list[Student], *, needs_graders: bool = False
) -> Workbook:
    """Open ``template`` and give each sheet with a username column the students.

    In such a sheet the students take the rows from ``EXAMPLE_ROW`` down, in
    roster order: each row gets the example row's formulas, moved to the row,
    and its formatting, but none of its plain values, comments or links; the
    username column gets the username and a ``grader`` or ``examiner`` column
    the student's grader. Sheets without a username column in their first row
    are left as they are. With ``needs_graders``, a template where no such
    sheet has a grader column is refused.
    """
    if not students:
        raise GraderError("the roster has no students")
    try:
        workbook = load_workbook(template)
    # SyntaxError covers the XML parsers' errors for a damaged file.
    except (InvalidFileException, zipfile.BadZipFile, KeyError, SyntaxError) as error:
        raise GraderError(f"{template} is not an Excel workbook: {error}") from None
    results = [_fill_sheet(sheet, students) for sheet in workbook.worksheets]
    filled = [has_graders for has_graders in results if has_graders is not None]
    if not filled:
        names = ", ".join(USERNAME_COLUMNS)
        raise GraderError(
            f"{template}: no sheet has a username column ({names}) in its first row"
        )
    if needs_graders and not any(filled):
        raise GraderError(
            f"{template}: no sheet with students has a grader or Examiner column "
            "for the --assistant split"
        )
    return workbook


def _fill_sheet(sheet: Worksheet, students: list[Student]) -> bool | None:
    """Write one row per student into ``sheet``; tell whether it has a grader column.

    None means the sheet has no username column and is left alone.
    """
    columns = {
        str(cell.value).strip().casefold(): cell.column
        for cell in sheet[1]
        if cell.value is not None
    }
    user_column = next((columns[n] for n in USERNAME_COLUMNS if n in columns), None)
    if user_column is None:
        return None
    grader_column = next((columns[n] for n in GRADER_HEADERS if n in columns), None)
    last_row = EXAMPLE_ROW + len(students) - 1
    needed = f"the {len(students)} students need rows {EXAMPLE_ROW}-{last_row}"
    for merged in sheet.merged_cells.ranges:
        if merged.min_row <= last_row and merged.max_row >= EXAMPLE_ROW:
            raise GraderError(
                f"{sheet.title}!{merged.coord} is merged, but {needed}; "
                "unmerge it or move it further down in the template"
            )
    for row in sheet.iter_rows(min_row=EXAMPLE_ROW + 1, max_row=last_row):
        for cell in row:
            if cell.value is not None or cell.comment is not None:
                raise GraderError(
                    f"{sheet.title}!{cell.coordinate} is not empty, but {needed}; "
                    "move what is there further down in the template"
                )
    example = [
        (cell.column, _example_formula(sheet, cell), copy(cell._style))
        for cell in sheet[EXAMPLE_ROW][: sheet.max_column]
    ]
    example_row = sheet.row_dimensions[EXAMPLE_ROW]
    for row, student in enumerate(students, start=EXAMPLE_ROW):
        for column, formula, style in example:
            cell = sheet.cell(row, column)
            cell._style = copy(style)
            cell.value = _formula_in_row(formula, column, row)
            cell.comment = cell.hyperlink = None
        sheet.cell(row, user_column).value = student.username
        if grader_column is not None:
            cell = sheet.cell(row, grader_column)
            cell.value = student.grader
            if student.grader is not None:
                cell.data_type = "s"  # a name starting with "=" stays text
        dimension = copy(example_row)  # height, hiding and row formatting
        dimension.index = row
        sheet.row_dimensions[row] = dimension
    return grader_column is not None


def _example_formula(sheet: Worksheet, cell: Cell) -> object:
    """Return the formula of the example row's ``cell``, or None for no formula.

    A data table, an array formula over several rows and a formula that
    openpyxl cannot parse are refused: they cannot be moved to other rows.
    """
    formula = cell.value if cell.data_type == "f" else None
    where = f"{sheet.title}!{cell.coordinate}"
    several_rows = False
    if isinstance(formula, ArrayFormula):
        _, first_row, _, last_row = range_boundaries(formula.ref)
        several_rows = first_row != last_row
    if several_rows or isinstance(formula, DataTableFormula):
        raise GraderError(
            f"{where}: an array formula over several rows or a data table "
            "cannot be copied to each student's row"
        )
    if formula is not None:
        text = formula.text if isinstance(formula, ArrayFormula) else formula
        try:
            Translator(text, cell.coordinate)
        except TokenizerError as error:
            raise GraderError(
                f"{where}: the formula cannot be copied: {error}"
            ) from None
    return formula


def _formula_in_row(formula: object, column: int, row: int) -> object:
    """Return the example row's ``formula`` moved to ``row``; None for no formula.

    Relative references move with the row; references with ``$`` stay.
    """
    if formula is None:
        return None
    letter = get_column_letter(column)
    origin, target = f"{letter}{EXAMPLE_ROW}", f"{letter}{row}"
    if isinstance(formula, ArrayFormula):
        first_column, _, last_column, _ = range_boundaries(formula.ref)
        first = f"{get_column_letter(first_column)}{row}"
        last = f"{get_column_letter(last_column)}{row}"
        text = Translator(formula.text, origin).translate_formula(target)
        return ArrayFormula(first if first == last else f"{first}:{last}", text)
    return Translator(formula, origin).translate_formula(target)
