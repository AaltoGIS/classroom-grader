"""Options and setup shared by the commands that work on a course's students."""

import argparse
import sys
from pathlib import Path

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


def submission_folder(settings: Settings, name: str, assignment: Assignment) -> Path:
    """Return ``submitted/<name>/<assignment>``, the nbgrader folder of a clone."""
    return settings.root / "submitted" / name / assignment.name
