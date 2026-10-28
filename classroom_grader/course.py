"""Options and setup shared by the commands that work on a course's students."""

import argparse
import sys
from collections.abc import Callable, Iterable, Sequence
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import TypeVar

from classroom_grader import GraderError
from classroom_grader.github import team_names
from classroom_grader.roster import Roster, Student, read_roster, select_students
from classroom_grader.settings import (
    Assignment,
    Settings,
    find_course_root,
    load_settings,
)


def add_course_option(parser: argparse.ArgumentParser) -> None:
    """Add ``--course`` to a command's parser."""
    parser.add_argument(
        "--course",
        type=Path,
        help="course folder (default: the nearest folder upwards with grader.toml)",
    )


def add_course_options(parser: argparse.ArgumentParser) -> None:
    """Add ``--course``, ``--grader`` and ``--student`` to a command's parser."""
    add_course_option(parser)
    parser.add_argument(
        "--grader",
        help="only this grader's students (default: grader in grader.toml)",
    )
    parser.add_argument(
        "--student",
        action="append",
        metavar="NAME",
        help="only this student, or team in a group assignment; repeat for more",
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


def course_settings(args: argparse.Namespace) -> Settings:
    """Load the settings of ``--course``, or of the course around the current folder."""
    root = args.course.resolve() if args.course else find_course_root(Path.cwd())
    return load_settings(root)


def open_course(args: argparse.Namespace) -> tuple[Settings, list[Student]]:
    """Load the course settings and the students selected by the course options.

    Usernames listed more than once in the roster are reported on stderr.
    """
    settings = course_settings(args)
    roster = _read_roster(settings)
    grader = args.grader or settings.grader
    return settings, select_students(roster.students, grader, args.student or ())


def open_assignments(
    args: argparse.Namespace,
) -> tuple[Settings, list[tuple[Assignment, list[str]]]]:
    """Load the settings and, per named assignment, the students or teams to handle.

    An individual assignment gets the roster's students (of ``--grader``); a
    group assignment gets the teams whose repositories are on GitHub, whatever
    ``--grader`` says.
    ``--student`` narrows both to the named students and teams; a name that
    matches none of them is an error, and so is a team whose folder would be a
    roster student's.
    """
    settings = course_settings(args)
    assignments = select_assignments(settings, args.assignments)
    roster = _read_roster(settings)
    students = []
    if any(assignment.type != "group" for assignment in assignments):
        grader = args.grader or settings.grader
        students = [s.username for s in select_students(roster.students, grader)]
    usernames = {student.username.casefold() for student in roster.students}
    wanted = {name.casefold() for name in args.student or ()}
    selection = []
    for assignment in assignments:
        names = students
        if assignment.type == "group":
            names = team_names(settings.organization, assignment.repo_prefix)
            if clashes := [team for team in names if team.casefold() in usernames]:
                raise GraderError(
                    f"{assignment.name}: the teams {', '.join(clashes)} have the "
                    "names of roster students, so they would share their folders "
                    "in submitted/; rename the teams on GitHub"
                )
            if not names:
                print(
                    f"grader: warning: no repositories named {assignment.repo_prefix}-*"
                    f" are visible in {settings.organization}",
                    file=sys.stderr,
                )
        selection.append(
            (
                assignment,
                [name for name in names if not wanted or name.casefold() in wanted],
            )
        )
    found = {name.casefold() for _, names in selection for name in names}
    if unknown := [name for name in args.student or () if name.casefold() not in found]:
        raise GraderError(f"no selected student or team is called {', '.join(unknown)}")
    return settings, selection


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


def _read_roster(settings: Settings) -> Roster:
    """Read the course roster, warning on stderr about usernames listed twice."""
    roster = read_roster(settings.roster, settings.username_column)
    for username in roster.duplicates:
        print(
            f"grader: warning: {username} is listed more than once in "
            f"{settings.roster}; using the first row",
            file=sys.stderr,
        )
    return roster
