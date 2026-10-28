"""``grader students``: the selected students and their local clones."""

import argparse

from classroom_grader.course import add_course_options, open_course, submission_folder
from classroom_grader.table import format_table

HELP = "List the selected students and the assignments they have a local clone of."


def add_arguments(parser: argparse.ArgumentParser) -> None:
    """Add the ``grader students`` options."""
    add_course_options(parser)


def run(args: argparse.Namespace) -> int:
    """Print one row per selected student: grader, and a column per assignment."""
    settings, students = open_course(args)
    assignments = [a for a in settings.assignments.values() if a.type == "individual"]
    rows = [
        [
            student.username,
            student.grader or "-",
            *(
                "cloned"
                if (submission_folder(settings, student.username, a) / ".git").exists()
                else "-"
                for a in assignments
            ),
        ]
        for student in students
    ]
    print(format_table(["Student", "Grader", *(a.name for a in assignments)], rows))
    print(f"\n{len(students)} student{'' if len(students) == 1 else 's'}")
    return 0
