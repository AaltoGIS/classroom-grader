"""The course roster: read the student CSV file and select students from it."""

import csv
import io
import re
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from classroom_grader import GraderError

USERNAME_COLUMNS = ("user", "username", "github", "github_name", "githubname")
GRADER_COLUMN = "grader"
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


def read_roster(path: Path, username_column: str | None = None) -> Roster:
    """Read a roster CSV file separated by commas, semicolons or tabs.

    The username column is ``username_column`` or else the first of
    ``USERNAME_COLUMNS`` found, matched case-insensitively. Rows without a
    username are skipped; a username listed again (in any case) keeps its first
    row and is reported in ``duplicates``. Usernames become folder names, so one
    that is not a GitHub username is an error.
    """
    text = _decode(path.read_bytes())
    rows = list(csv.reader(io.StringIO(text), delimiter=_delimiter(text)))
    if not rows:
        raise GraderError(f"{path} is empty")
    header = [cell.strip().casefold() for cell in rows[0]]
    wanted = (
        [username_column.strip().casefold()] if username_column else USERNAME_COLUMNS
    )
    user_index = next((header.index(name) for name in wanted if name in header), None)
    if user_index is None:
        what = repr(username_column) if username_column else ", ".join(wanted)
        raise GraderError(
            f"{path} has no username column ({what}); its columns are: "
            f"{', '.join(rows[0])}. Set username_column in grader.toml"
        )
    grader_index = header.index(GRADER_COLUMN) if GRADER_COLUMN in header else None
    students: list[Student] = []
    duplicates: list[str] = []
    seen: set[str] = set()
    invalid: list[str] = []
    for number, row in enumerate(rows[1:], start=2):
        username = _cell(row, user_index)
        if not username:
            continue
        if not _USERNAME.fullmatch(username):
            invalid.append(f"row {number}: {username!r}")
        elif username.casefold() in seen:
            duplicates.append(username)
        else:
            seen.add(username.casefold())
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


def _decode(data: bytes) -> str:
    """Decode a roster as UTF-8 (with or without a BOM), else as Windows-1252."""
    for encoding in ("utf-8-sig", "cp1252"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            pass
    return data.decode("latin-1")


def _delimiter(text: str) -> str:
    """Guess the roster's delimiter among comma, semicolon and tab; default comma."""
    try:
        return csv.Sniffer().sniff(text[:4096], delimiters=",;\t").delimiter
    except csv.Error:
        return ","


def _cell(row: list[str], index: int | None) -> str:
    """Return the stripped cell at ``index``, or "" when the row is shorter."""
    return row[index].strip() if index is not None and index < len(row) else ""
