"""The course roster: read the student CSV file and select students from it."""

import codecs
import csv
import io
import re
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from pathlib import Path

from classroom_grader import GraderError

USERNAME_COLUMNS = ("user", "username", "github", "github_name", "githubname")
GRADER_COLUMN = "grader"
# Classroom 50's roster.csv also lists staff, with role ta, hta or teacher.
ROLE_COLUMN = "role"
STUDENT_ROLE = "student"
# GitHub usernames, plus the underscore of Enterprise managed-user names.
_USERNAME = re.compile(r"[A-Za-z0-9_-]+")


@dataclass(frozen=True)
class Student:
    """A roster row: the GitHub username and the assistant who grades the student."""

    username: str
    grader: str | None


@dataclass(frozen=True)
class Roster:
    """The students of a roster file in file order, and the usernames listed twice."""

    students: list[Student]
    duplicates: list[str]


@dataclass(frozen=True)
class _CsvFile:
    """A roster file's rows, with what is needed to write it back the same way."""

    rows: list[list[str]]
    delimiter: str
    encoding: str
    newline: str
    final_newline: bool


def read_roster(path: Path, username_column: str | None = None) -> Roster:
    """Read a roster CSV file separated by commas, semicolons or tabs.

    The username column is ``username_column`` or else the first of
    ``USERNAME_COLUMNS`` found, matched case-insensitively. Rows without a
    username are skipped, and so are rows whose ``role`` column names another
    role than ``student``; a username listed again (in any case) keeps its first
    row and is reported in ``duplicates``. Usernames become folder names, so one
    that is not a GitHub username is an error.
    """
    table = _read_csv(path)
    header = [cell.strip().casefold() for cell in table.rows[0]]
    grader_index = header.index(GRADER_COLUMN) if GRADER_COLUMN in header else None
    students: list[Student] = []
    duplicates: list[str] = []
    invalid: list[str] = []
    for number, row, username, first in _student_rows(path, table, username_column):
        if not _USERNAME.fullmatch(username):
            invalid.append(f"row {number}: {username!r}")
        elif not first:
            duplicates.append(username)
        else:
            students.append(Student(username, _cell(row, grader_index) or None))
    if invalid:
        raise GraderError(
            f"{path} has usernames that are not GitHub usernames: {'; '.join(invalid)}"
        )
    return Roster(students, duplicates)


def select_students(
    students: list[Student], grader: str | None = None, names: Sequence[str] = ()
) -> list[Student]:
    """Return the students of ``grader`` and, when ``names`` is given, only those.

    Graders and names match case-insensitively. A grader without students, or a
    name that is not among the grader's students, is an error.
    """
    if grader is not None:
        spellings: dict[str, str] = {}
        for student in students:
            if student.grader:
                spellings.setdefault(student.grader.casefold(), student.grader)
        graders = sorted(spellings.values(), key=str.casefold)
        if not graders:
            raise GraderError(
                f"the roster names no graders, so --grader {grader} fits nobody"
            )
        students = [
            s for s in students if s.grader and s.grader.casefold() == grader.casefold()
        ]
        if not students:
            raise GraderError(
                f"no students for grader {grader}; graders in the roster: "
                f"{', '.join(graders)}"
            )
    if names:
        wanted = {name.casefold() for name in names}
        known = {s.username.casefold() for s in students}
        unknown = [name for name in names if name.casefold() not in known]
        if unknown:
            scope = f" for grader {grader}" if grader else ""
            raise GraderError(f"not in the roster{scope}: {', '.join(unknown)}")
        students = [s for s in students if s.username.casefold() in wanted]
    return students


def split_between(students: list[Student], graders: Sequence[str]) -> list[Student]:
    """Give each of ``graders`` a block of consecutive students.

    The blocks follow the order of ``students`` and of ``graders``; their sizes
    differ by at most one, the first graders getting the larger blocks.
    """
    size, extra = divmod(len(students), len(graders))
    split: list[Student] = []
    for number, grader in enumerate(graders):
        block = students[len(split) : len(split) + size + (number < extra)]
        split += [Student(student.username, grader) for student in block]
    return split


def roster_with_graders(
    path: Path, graders: dict[str, str], username_column: str | None = None
) -> bytes:
    """Return the roster file with ``graders`` written into its ``grader`` column.

    ``graders`` maps casefolded usernames to graders; only the rows that
    ``read_roster`` takes as students get one. A missing column is added after
    the widest row. The other cells, the separator, the encoding and the line
    endings stay as they were.
    """
    table = _read_csv(path)
    header = [cell.strip().casefold() for cell in table.rows[0]]
    if GRADER_COLUMN in header:
        grader_index = header.index(GRADER_COLUMN)
    else:
        grader_index = max(len(row) for row in table.rows)
        padding = [""] * (grader_index - len(table.rows[0]))
        table.rows[0].extend([*padding, GRADER_COLUMN])
    for _, row, username, first in _student_rows(path, table, username_column):
        grader = graders.get(username.casefold())
        if first and grader is not None:
            row.extend([""] * (grader_index + 1 - len(row)))
            row[grader_index] = grader
    text = io.StringIO()
    writer = csv.writer(text, delimiter=table.delimiter, lineterminator=table.newline)
    writer.writerows(table.rows)
    written = text.getvalue()
    if not table.final_newline:
        written = written.removesuffix(table.newline)
    try:
        return written.encode(table.encoding)
    except UnicodeEncodeError:
        raise GraderError(
            f"{path}: a grader's name cannot be written in its encoding, "
            f"{table.encoding}"
        ) from None


def _read_csv(path: Path) -> _CsvFile:
    """Read a roster's rows, guessing its encoding, separator and line endings."""
    text, encoding = _decode(path.read_bytes())
    delimiter = _delimiter(text)
    # newline="" keeps each line's ending, so rows can end at CR, LF or CRLF.
    lines = io.StringIO(text, newline="").readlines()
    reader = csv.reader(lines, delimiter=delimiter)
    header = next(reader, None)
    if header is None:
        raise GraderError(f"{path} is empty")
    # The header's last line, past any line break inside a quoted cell.
    header_end = lines[reader.line_num - 1]
    endings = ("\r\n", "\r", "\n")
    newline = next((end for end in endings if header_end.endswith(end)), "\n")
    rows = [header, *reader]
    return _CsvFile(rows, delimiter, encoding, newline, text.endswith(endings))


def _student_rows(
    path: Path, table: _CsvFile, username_column: str | None
) -> Iterator[tuple[int, list[str], str, bool]]:
    """Yield each student row's number, cells, username and whether it comes first.

    Rows without a username and rows whose ``role`` is another than
    ``student`` are left out; a username listed again, in any case, is not
    first.
    """
    header = [cell.strip().casefold() for cell in table.rows[0]]
    user_index = _username_index(path, table.rows[0], username_column)
    role_index = header.index(ROLE_COLUMN) if ROLE_COLUMN in header else None
    seen: set[str] = set()
    for number, row in enumerate(table.rows[1:], start=2):
        username = _cell(row, user_index)
        if username and _cell(row, role_index).casefold() in ("", STUDENT_ROLE):
            yield number, row, username, username.casefold() not in seen
            seen.add(username.casefold())


def _username_index(path: Path, header: list[str], username_column: str | None) -> int:
    """Return the index of the username column in the roster's ``header`` row."""
    names = [cell.strip().casefold() for cell in header]
    wanted = (
        [username_column.strip().casefold()] if username_column else USERNAME_COLUMNS
    )
    index = next((names.index(name) for name in wanted if name in names), None)
    if index is None:
        what = repr(username_column) if username_column else ", ".join(wanted)
        raise GraderError(
            f"{path} has no username column ({what}); its columns are: "
            f"{', '.join(header)}. Set username_column in grader.toml"
        )
    return index


def _decode(data: bytes) -> tuple[str, str]:
    """Decode a roster as UTF-8 (with or without a BOM), else as Windows-1252.

    Return the text and the encoding that decoded it.
    """
    utf8 = "utf-8-sig" if data.startswith(codecs.BOM_UTF8) else "utf-8"
    for encoding in (utf8, "cp1252"):
        try:
            return data.decode(encoding), encoding
        except UnicodeDecodeError:
            pass
    return data.decode("latin-1"), "latin-1"


def _delimiter(text: str) -> str:
    """Return the comma, semicolon or tab that splits the header row the most.

    The header names every column, so it holds the delimiter however the rows
    below differ in width. A tie, as in a header of one column, gives the comma.
    """

    def header_width(delimiter: str) -> int:
        rows = csv.reader(io.StringIO(text, newline=""), delimiter=delimiter)
        return len(next(rows, []))

    return max(",;\t", key=header_width)


def _cell(row: list[str], index: int | None) -> str:
    """Return the stripped cell at ``index``, or "" when the row is shorter."""
    return row[index].strip() if index is not None and index < len(row) else ""
