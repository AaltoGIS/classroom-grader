"""``grader source``: the teacher's repository into ``source/``, and its release."""

import argparse
import os
import shutil
import subprocess
import sys

from classroom_grader import GraderError
from classroom_grader.course import (
    add_course_option,
    course_settings,
    select_assignments,
)
from classroom_grader.git import GitError
from classroom_grader.github import repo_url
from classroom_grader.repo import (
    clone_into,
    clone_problem,
    fast_forward,
    is_unfetched,
    leads_outside,
)
from classroom_grader.settings import Assignment, Settings

HELP = "Clone or update the teacher's repositories and release them with nbgrader."


def add_arguments(parser: argparse.ArgumentParser) -> None:
    """Add the ``grader source`` arguments."""
    parser.add_argument(
        "assignments", nargs="+", metavar="ASSIGNMENT", help="assignment in grader.toml"
    )
    add_course_option(parser)
    parser.add_argument(
        "--force",
        action="store_true",
        help="let nbgrader replace an existing release/<ASSIGNMENT>",
    )


def run(args: argparse.Namespace) -> int:
    """Update each assignment's source and run nbgrader; 1 if any assignment failed.

    Nothing is pushed anywhere.
    """
    settings = course_settings(args)
    assignments = select_assignments(settings, args.assignments)
    nbgrader = shutil.which("nbgrader")
    if nbgrader is None:
        raise GraderError(
            "nbgrader is not on PATH; activate the course's Python environment first"
        )
    nbgrader = os.path.abspath(nbgrader)  # it runs from the course folder
    failed = False
    for assignment in assignments:
        try:
            state = update_source(settings, assignment)
            print(f"{assignment.name}: {assignment.source_repo} {state}")
            run_nbgrader(
                nbgrader, ["db", "assignment", "add", assignment.name], settings
            )
            release = ["generate_assignment", assignment.name]
            run_nbgrader(
                nbgrader, release + (["--force"] if args.force else []), settings
            )
        # RuntimeError: a symlink loop on Python 3.11
        except (GraderError, OSError, RuntimeError) as error:
            print(f"{assignment.name}: {error}", file=sys.stderr)
            failed = True
    return 1 if failed else 0


def update_source(settings: Settings, assignment: Assignment) -> str:
    """Clone or fast-forward ``source/<assignment>``; return what was done.

    An existing clone must have the source repository as origin, in its HTTPS
    or SSH form.
    """
    folder = settings.root / "source" / assignment.name
    owner, _, repo = assignment.source_repo.partition("/")
    if (problem := leads_outside(folder, settings.root / "source")) is not None:
        raise GraderError(problem)
    try:
        if is_unfetched(folder):
            clone_into(repo_url(owner, repo, settings.protocol), folder)
            return "cloned into source/"
        if (problem := clone_problem(folder, owner, repo)) is not None:
            raise GraderError(f"source/{assignment.name} is not used: {problem}")
        state, detail = fast_forward(folder)
    except GitError as error:
        raise GraderError(f"{assignment.source_repo}: {error}") from None
    return f"{state} ({detail})" if detail else state


def run_nbgrader(nbgrader: str, args: list[str], settings: Settings) -> None:
    """Run ``nbgrader <args>`` in the course folder, showing its output."""
    result = subprocess.run(
        [nbgrader, *args], cwd=settings.root, stdin=subprocess.DEVNULL, check=False
    )
    if result.returncode != 0:
        raise GraderError(
            f"nbgrader {' '.join(args)} failed with exit code {result.returncode}"
        )
