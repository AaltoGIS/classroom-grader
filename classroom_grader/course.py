"""Options and setup shared by the commands that work on a course's students."""

import argparse
import sys
from collections.abc import Callable, Iterable, Sequence
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import TypeVar

from classroom_grader import GraderError
from classroom_grader.roster import Student, read_roster, select_students
from classroom_grader.settings import (
    Assignment,
    Settings,
    find_course_root,
    load_settings,
)


def add_course_options(parser: argparse.ArgumentParser) -> None:
    """Add ``--course``, ``--grader`` and ``--student`` to a command's parser."""
    parser.add_argument(
        "--course",
        type=Path,
        help="course folder (default: the nearest folder upwards with grader.toml)",
    )
    parser.add_argument(
        "--grader",
        help="only this grader's students (default: grader in grader.toml)",
    )
    parser.add_argument(
        "--student",
        action="append",
        metavar="NAME",
        help="only this student; repeat for more",
    )


def add_repo_options(parser: argparse.ArgumentParser) -> None:
    """Add the assignments, the course options and ``--jobs`` to a command's parser."""
    parser.add_argument(
        "assignments", nargs="+", metavar="ASSIGNMENT", help="assignment in grader.toml"
    )
    add_course_options(parser)
    parser.add_argument(
        "--jobs",
        type=_positive_int,
        default=8,
        help="repositories handled at the same time (default: 8)",
    )


def open_course(args: argparse.Namespace) -> tuple[Settings, list[Student]]:
    """Load the course settings and the students selected by the course options.

    Usernames listed more than once in the roster are reported on stderr.
    """
    root = args.course.resolve() if args.course else find_course_root(Path.cwd())
    settings = load_settings(root)
    roster = read_roster(settings.roster, settings.username_column)
    for username in roster.duplicates:
        print(
            f"grader: warning: {username} is listed more than once in "
            f"{settings.roster}; using the first row",
            file=sys.stderr,
        )
    grader = args.grader or settings.grader
    return settings, select_students(roster.students, grader, args.student or ())


def select_assignments(settings: Settings, names: Sequence[str]) -> list[Assignment]:
    """Return the named assignments, matched case-insensitively, without repeats."""
    by_name = {name.casefold(): a for name, a in settings.assignments.items()}
    unknown = [name for name in names if name.casefold() not in by_name]
    if unknown:
        known = ", ".join(settings.assignments) or "none"
        raise GraderError(
            f"not in grader.toml: {', '.join(unknown)}; its assignments: {known}"
        )
    return list(
        {
            by_name[name.casefold()].name: by_name[name.casefold()] for name in names
        }.values()
    )


def individual_assignments(
    settings: Settings, names: Sequence[str], command: str
) -> list[Assignment]:
    """Return the named assignments; a group assignment is an error for ``command``."""
    assignments = select_assignments(settings, names)
    for assignment in assignments:
        if assignment.type == "group":
            raise GraderError(
                f"{assignment.name} is a group assignment; grader {command} does not "
                "handle team repositories yet"
            )
    return assignments


Item = TypeVar("Item")
Result = TypeVar("Result")


def map_in_parallel(
    function: Callable[[Item], Result], items: Iterable[Item], jobs: int
) -> list[Result]:
    """Return ``function`` of each item in order, running ``jobs`` at a time."""
    with ThreadPoolExecutor(max_workers=jobs) as pool:
        return list(pool.map(function, items))


def submission_folder(settings: Settings, name: str, assignment: Assignment) -> Path:
    """Return ``submitted/<name>/<assignment>``, the nbgrader folder of a clone."""
    return settings.root / "submitted" / name / assignment.name


def _positive_int(text: str) -> int:
    """Parse ``--jobs``, a whole number of at least 1."""
    if not text.isdigit() or int(text) < 1:
        raise argparse.ArgumentTypeError(
            f"{text!r} is not a whole number of at least 1"
        )
    return int(text)
