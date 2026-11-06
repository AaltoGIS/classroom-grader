"""Course settings: find, read and check ``grader.toml``."""

import math
import re
import tomllib
import unicodedata
from dataclasses import dataclass, field, fields
from datetime import datetime
from pathlib import Path, PureWindowsPath
from typing import Any

from classroom_grader import GraderError
from classroom_grader.table import printable

SETTINGS_FILE = "grader.toml"
DEFAULT_FEEDBACK_FILES = ("README.md",)
ASSIGNMENT_TYPES = ("individual", "group")
PROTOCOLS = ("https", "ssh")
GRADES = 5
DEFAULT_QUIZ_PASS_SHARE = 0.5
DEFAULT_GRADE_LIMITS = (0.9, 0.8, 0.7, 0.6, 0.5)
LIMITS_SHEET = "Limits"
# The grading template that grader template adds to the students' READMEs.
DEFAULT_TEMPLATE_TEXT = """\
## Grading
**Points:**
{problems}

**Total: /{total} points**

Comments:

{comment}
"""
DEFAULT_PROBLEM_LINE = "- {name}: /{points} points"
DEFAULT_COMMENT = "Good job!"
# The spreadsheet's columns around the exercises and the quizzes.
SHEET_FIRST_COLUMNS = (
    "user",
    "Lastname",
    "Firstname",
    "Examiner",
    "Comments / Requires Checking?",
)
SHEET_MIDDLE_COLUMNS = ("Feedback given", "Exercises Total")
SHEET_LAST_COLUMNS = (
    "Quizzes total",
    "Quiz points (scaled)",
    "Extra points (attendance)",
    "Total points",
    "Total grade",
)

_EXCEL_SHEET_FORBIDDEN = set("[]:*?/\\")
_EXCEL_SHEET_MAX_LENGTH = 31
_GITHUB_OWNER = re.compile(r"[A-Za-z0-9-]+")
_GITHUB_REPO = re.compile(r"[A-Za-z0-9._-]+")
_OWNER_AND_REPO = re.compile(rf"{_GITHUB_OWNER.pattern}/{_GITHUB_REPO.pattern}")
_REPO_NAME = "a GitHub repository name"
_OWNER_REPO = "<owner>/<repository>"
_WINDOWS_FORBIDDEN = set('<>:"/\\|?*')
_WINDOWS_RESERVED = {"CON", "PRN", "AUX", "NUL"} | {
    f"{port}{n}" for port in ("COM", "LPT") for n in "123456789\u00b9\u00b2\u00b3"
}


class SettingsError(GraderError):
    """Invalid settings; ``problems`` holds one line per problem, key name first."""

    def __init__(self, problems: list[str], source: Path | None = None):
        self.problems = problems
        where = f" in {source}" if source else ""
        lines = "\n".join(f"  {problem}" for problem in problems)
        super().__init__(f"invalid settings{where}:\n{lines}")


@dataclass(frozen=True)
class Assignment:
    """One ``[assignments.<name>]`` table; ``name`` is the local folder name."""

    name: str
    type: str
    repo_prefix: str
    source_repo: str
    deadline: datetime | None
    points: dict[str, int | float] = field(default_factory=dict)
    comment: str | None = None

    @property
    def owner_title(self) -> str:
        """Who has one repository of the assignment: ``Student`` or ``Team``."""
        return "Team" if self.type == "group" else "Student"


@dataclass(frozen=True)
class GradingSheet:
    """The ``[grading_sheet]`` table: what ``grader grading-sheet`` writes."""

    name: str
    exercises: dict[str, int | float]
    quizzes: tuple[str, ...]
    quiz_max_points: int | float
    quiz_pass_share: int | float
    grade_limits: tuple[int | float, ...]


@dataclass(frozen=True)
class GradingTemplate:
    """The ``[grading_template]`` table: the layout ``grader template`` writes.

    ``text`` holds ``{problems}`` and can hold ``{total}`` and ``{comment}``;
    ``problem`` is the line for each problem, with ``{name}`` and ``{points}``.
    """

    text: str = DEFAULT_TEMPLATE_TEXT
    problem: str = DEFAULT_PROBLEM_LINE
    comment: str = DEFAULT_COMMENT


@dataclass(frozen=True)
class Settings:
    """The checked contents of ``grader.toml``, with defaults filled in."""

    root: Path
    organization: str
    classroom: str | None
    roster: Path
    username_column: str | None
    grader: str | None
    feedback_files: tuple[str, ...]
    protocol: str
    assignments: dict[str, Assignment]
    grading_sheet: GradingSheet | None
    grading_template: GradingTemplate = GradingTemplate()


SETTING_KEYS = {field.name for field in fields(Settings)} - {"root"}
ASSIGNMENT_KEYS = {field.name for field in fields(Assignment)} - {"name"}
GRADING_SHEET_KEYS = {field.name for field in fields(GradingSheet)}
GRADING_TEMPLATE_KEYS = {field.name for field in fields(GradingTemplate)}


def find_course_root(start: Path) -> Path:
    """Return the nearest folder from ``start`` upwards that holds ``grader.toml``."""
    start = start.resolve()
    for folder in (start, *start.parents):
        if (folder / SETTINGS_FILE).is_file():
            return folder
    raise GraderError(
        f"no {SETTINGS_FILE} in {start} or its parent folders; go to your course "
        "folder or pass --course; to start a new course, run grader init"
    )


def load_settings(root: Path) -> Settings:
    """Read and check ``grader.toml`` in the course folder ``root``."""
    path = root / SETTINGS_FILE
    try:
        with path.open("rb") as file:
            data = tomllib.load(file)
    except FileNotFoundError:
        raise GraderError(f"{path} not found") from None
    except UnicodeDecodeError:
        raise GraderError(f"{path} is not UTF-8 text; save it as UTF-8") from None
    except OSError as exc:
        raise GraderError(f"cannot read {path}: {exc.strerror or exc}") from None
    except tomllib.TOMLDecodeError as exc:
        raise SettingsError([str(exc)], path) from None
    return parse_settings(data, root, path)


def parse_settings(
    data: dict[str, Any], root: Path, source: Path | None = None
) -> Settings:
    """Check settings parsed from TOML and fill in defaults.

    Raises ``SettingsError`` listing every problem found, not only the first.
    """
    problems = [
        f"{printable(key)}: unknown setting"
        for key in sorted(data.keys() - SETTING_KEYS)
    ]
    organization = _string(data, "organization", problems, required=True)
    if organization is not None and not _GITHUB_OWNER.fullmatch(organization):
        problems.append(
            f"organization: {organization!r} is not a GitHub organization name"
        )
    classroom = _string(data, "classroom", problems)
    if classroom is not None and not _GITHUB_REPO.fullmatch(classroom):
        problems.append(f"classroom: {classroom!r} cannot start a repository name")
        classroom = None
    roster_name = _string(data, "roster", problems, required=True)
    if roster_name is not None and not (root / roster_name).is_file():
        problems.append(f"roster: file not found: {root / roster_name}")
    username_column = _string(data, "username_column", problems)
    grader = _string(data, "grader", problems)
    feedback_files = _feedback_files(data.get("feedback_files"), problems)
    protocol = _string(data, "protocol", problems) or "https"
    if protocol not in PROTOCOLS:
        problems.append(f"protocol: must be one of {', '.join(PROTOCOLS)}")
    assignments = _assignments(
        data.get("assignments", {}), organization, classroom, problems
    )
    grading_sheet = _grading_sheet(data.get("grading_sheet"), problems)
    grading_template = _grading_template(data.get("grading_template"), problems)
    if problems:
        raise SettingsError(problems, source)
    return Settings(
        root=root,
        organization=organization,
        classroom=classroom,
        roster=root / roster_name,
        username_column=username_column,
        grader=grader,
        feedback_files=feedback_files,
        protocol=protocol,
        assignments=assignments,
        grading_sheet=grading_sheet,
        grading_template=grading_template,
    )


def _string(
    table: dict, key: str, problems: list[str], prefix: str = "", required: bool = False
) -> str | None:
    """Return ``table[key]`` if it is a non-empty string, else record a problem."""
    value, label = table.get(key), prefix + key
    if value is None:
        if required:
            problems.append(f"{label}: missing")
        return None
    if not isinstance(value, str) or not value.strip() or not value.isprintable():
        problems.append(f"{label}: must be non-empty printable text")
        return None
    return value


def _feedback_files(value: Any, problems: list[str]) -> tuple[str, ...]:
    """Return the ``feedback_files`` paths in git's form, or the default."""
    if value is None:
        return DEFAULT_FEEDBACK_FILES
    if not isinstance(value, list) or not value:
        problems.append("feedback_files: must be a list of file paths")
        return ()
    return repository_paths(value, "feedback_files", problems)


def repository_paths(
    value: list[Any], label: str, problems: list[str]
) -> tuple[str, ...]:
    """Return file paths in git's form: relative, with forward slashes.

    ``./README.md`` becomes ``README.md`` and ``feedback\\notes.md`` becomes
    ``feedback/notes.md``. A path that leaves the repository, passes through a
    ``.git`` folder, or has a part that cannot be a file name on every system
    is a problem, recorded under ``label``.
    """
    paths = []
    for path in value:
        parts = PureWindowsPath(path).parts if isinstance(path, str) else ()
        inside = [part for part in parts if part != "."]
        if (
            not isinstance(path, str)
            or not path.strip()
            or not path.isprintable()
            or PureWindowsPath(path).anchor
            or ".." in parts
            or not inside
            or any(
                part.casefold() == ".git" or folder_name_problem(part)
                for part in inside
            )
        ):
            problems.append(f"{label}: {path!r} is not a path inside the repository")
        else:
            paths.append("/".join(part for part in parts if part != "."))
    return tuple(paths)


def _assignments(
    table: Any, organization: str | None, classroom: str | None, problems: list[str]
) -> dict[str, Assignment]:
    """Check the ``[assignments.<name>]`` tables and fill in their defaults.

    The default ``repo_prefix`` is ``<classroom>-<name>`` in lower case, the
    start of Classroom 50's repository names, or ``<name>`` without a classroom.
    """
    if not isinstance(table, dict):
        problems.append("assignments: must be a table of assignment tables")
        return {}
    assignments = {}
    folded: dict[tuple[str, str], str] = {}
    for name, entry in table.items():
        label = f"assignments.{printable(name)}"
        if (reason := folder_name_problem(name)) is not None:
            problems.append(f"{label}: {reason}")
        # Windows compares folder names by uppercase, macOS by case folding.
        nfc = unicodedata.normalize("NFC", name)
        keys = (("upper", nfc.upper()), ("fold", nfc.casefold()))
        for other in sorted({folded.setdefault(key, name) for key in keys} - {name}):
            problems.append(
                f"{label}: Windows or macOS treat it as the same folder name as "
                f"assignments.{printable(other)}"
            )
        if not isinstance(entry, dict):
            problems.append(f"{label}: must be a table")
            continue
        problems.extend(
            f"{label}.{printable(key)}: unknown setting"
            for key in sorted(entry.keys() - ASSIGNMENT_KEYS)
        )
        kind = _string(entry, "type", problems, f"{label}.") or "individual"
        if kind not in ASSIGNMENT_TYPES:
            problems.append(
                f"{label}.type: must be one of {', '.join(ASSIGNMENT_TYPES)}"
            )
        given_prefix = _string(entry, "repo_prefix", problems, f"{label}.")
        repo_prefix = (
            given_prefix or (f"{classroom}-{name}" if classroom else name).lower()
        )
        if not _GITHUB_REPO.fullmatch(repo_prefix):
            problems.append(
                _invalid(label, "repo_prefix", repo_prefix, given_prefix, _REPO_NAME)
            )
        given_source = _string(entry, "source_repo", problems, f"{label}.")
        source_repo = given_source or f"{organization}/{name}-grading"
        if (given_source or organization) and not _OWNER_AND_REPO.fullmatch(
            source_repo
        ):
            problems.append(
                _invalid(label, "source_repo", source_repo, given_source, _OWNER_REPO)
            )
        deadline = entry.get("deadline")
        if deadline is not None and not isinstance(deadline, datetime):
            problems.append(
                f"{label}.deadline: must be a date and time with a time zone, "
                "such as 2026-11-13T23:59:00+02:00"
            )
        elif deadline is not None and deadline.tzinfo is None:
            problems.append(f"{label}.deadline: add a time zone, such as +02:00")
        points = entry.get("points", {})
        if not isinstance(points, dict) or not all(
            _is_line(problem) and _is_positive(value)
            for problem, value in points.items()
        ):
            problems.append(
                f"{label}.points: must give each problem its maximum points, "
                'such as { "Problem 1" = 8 }'
            )
            points = {}
        comment = _string(entry, "comment", problems, f"{label}.")
        assignments[name] = Assignment(
            name, kind, repo_prefix, source_repo, deadline, points, comment
        )
    return assignments


def _grading_sheet(table: Any, problems: list[str]) -> GradingSheet | None:
    """Check the ``[grading_sheet]`` table; None when the course has none."""
    if table is None:
        return None
    if not isinstance(table, dict):
        problems.append("grading_sheet: must be a table")
        return None
    label = "grading_sheet."
    problems_before = len(problems)
    problems.extend(
        f"{label}{printable(key)}: unknown setting"
        for key in sorted(table.keys() - GRADING_SHEET_KEYS)
    )
    name = _string(table, "name", problems, label, required=True)
    if name is not None and (
        len(name) > _EXCEL_SHEET_MAX_LENGTH
        or _EXCEL_SHEET_FORBIDDEN & set(name)
        or name.strip("'") != name
        or name.casefold() == LIMITS_SHEET.casefold()
    ):
        forbidden = " ".join(sorted(_EXCEL_SHEET_FORBIDDEN))
        problems.append(
            f"{label}name: {name!r} cannot name the sheet: it needs at most "
            f"{_EXCEL_SHEET_MAX_LENGTH} characters, none of {forbidden}, no ' at "
            f"either end, and another name than {LIMITS_SHEET}"
        )
    exercises = table.get("exercises")
    exercises_valid = (
        isinstance(exercises, dict)
        and bool(exercises)
        and all(_is_line(name) for name in exercises)
        and all(_is_positive(points) for points in exercises.values())
    )
    if not exercises_valid:
        problems.append(
            f"{label}exercises: must give each column its maximum points, "
            "such as { Ex1 = 20 }"
        )
    quizzes = table.get("quizzes")
    quizzes_valid = (
        isinstance(quizzes, list)
        and bool(quizzes)
        and all(_is_line(name) for name in quizzes)
    )
    if not quizzes_valid:
        problems.append(f"{label}quizzes: must be a list of column names")
    if exercises_valid and quizzes_valid:
        columns = [
            *SHEET_FIRST_COLUMNS,
            *exercises,
            *SHEET_MIDDLE_COLUMNS,
            *quizzes,
            *SHEET_LAST_COLUMNS,
        ]
        if len({column.strip().casefold() for column in columns}) < len(columns):
            problems.append(
                "grading_sheet: each exercise and quiz needs a column name of its "
                "own, also different from the sheet's other columns"
            )
    quiz_max_points = table.get("quiz_max_points")
    if not _is_positive(quiz_max_points):
        problems.append(f"{label}quiz_max_points: must be a number above 0")
    quiz_pass_share = table.get("quiz_pass_share", DEFAULT_QUIZ_PASS_SHARE)
    if not _is_share(quiz_pass_share):
        problems.append(f"{label}quiz_pass_share: must be above 0 and at most 1")
    limits = table.get("grade_limits", list(DEFAULT_GRADE_LIMITS))
    if (
        not isinstance(limits, list)
        or len(limits) != GRADES
        or not all(_is_share(share) for share in limits)
        or limits != sorted(set(limits), reverse=True)
    ):
        problems.append(
            f"{label}grade_limits: must be {GRADES} shares of the total points, "
            "above 0 and at most 1, for grades 5 to 1, highest first"
        )
    if len(problems) > problems_before:
        return None
    return GradingSheet(
        name, exercises, tuple(quizzes), quiz_max_points, quiz_pass_share, tuple(limits)
    )


def _grading_template(table: Any, problems: list[str]) -> GradingTemplate:
    """Check the ``[grading_template]`` table and fill in the defaults."""
    if table is None:
        return GradingTemplate()
    if not isinstance(table, dict):
        problems.append("grading_template: must be a table")
        return GradingTemplate()
    label = "grading_template."
    problems.extend(
        f"{label}{printable(key)}: unknown setting"
        for key in sorted(table.keys() - GRADING_TEMPLATE_KEYS)
    )
    text = table.get("text", DEFAULT_TEMPLATE_TEXT)
    if isinstance(text, str) and not all(
        char.isprintable() or char in "\n\r\t" for char in text
    ):
        problems.append(f"{label}text: must be printable text")
    heading = template_heading(text) if isinstance(text, str) else None
    if heading is None or "{problems}" not in [
        line.strip() for line in text.splitlines()
    ]:
        problems.append(
            f"{label}text: must hold {{problems}} on a line of its own and start "
            "with a line of plain text, such as ## Grading, which marks a README "
            "that has the template"
        )
    problem = table.get("problem", DEFAULT_PROBLEM_LINE)
    if not _is_line(problem) or not {"{name}", "{points}"} <= set(
        re.findall(r"\{\w+\}", problem)
    ):
        problems.append(
            f"{label}problem: must be one line that holds {{name}} and {{points}}"
        )
    comment = _string(table, "comment", problems, label) or DEFAULT_COMMENT
    return GradingTemplate(text, problem, comment)


def template_heading(text: str) -> str | None:
    """Return the first line of a template text with something on it.

    None when that line holds a placeholder, which would change from one
    README to the next.
    """
    line = next((line.strip() for line in text.splitlines() if line.strip()), "")
    if not line or re.search(r"\{(problems|total|comment)\}", line):
        return None
    return line


def _is_line(value: Any) -> bool:
    """Tell whether ``value`` is non-empty printable text on one line.

    Such text can also head a spreadsheet column.
    """
    return isinstance(value, str) and bool(value.strip()) and value.isprintable()


def _is_positive(value: Any) -> bool:
    """Tell whether ``value`` is a finite number above 0."""
    return (
        isinstance(value, int | float)
        and not isinstance(value, bool)
        and 0 < value < math.inf
    )


def _is_share(value: Any) -> bool:
    """Tell whether ``value`` is a number above 0 and at most 1."""
    return _is_positive(value) and value <= 1


def _invalid(label: str, key: str, value: str, given: str | None, kind: str) -> str:
    """Describe a ``key`` value that is not ``kind``; a bad default asks to set it."""
    if given:
        return f"{label}.{key}: {value!r} is not {kind}"
    return f"{label}.{key}: the default {value!r} is not {kind}; set {key}"


def folder_name_problem(name: str) -> str | None:
    """Say why ``name`` cannot be a folder name on Windows, macOS and Linux."""
    if not name.strip() or name in (".", ".."):
        return "not a folder name"
    bad = sorted(
        {char for char in name if char in _WINDOWS_FORBIDDEN or not char.isprintable()}
    )
    if bad:
        return f"folder names cannot contain {' '.join(repr(char) for char in bad)}"
    if len(name.encode()) > 255:
        return "folder names can be at most 255 bytes long"
    if name[-1] in " .":
        return "folder names cannot end with a space or a dot on Windows"
    if name.split(".")[0].strip().upper() in _WINDOWS_RESERVED:
        return "reserved name on Windows"
    return None
