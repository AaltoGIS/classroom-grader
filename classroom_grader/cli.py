"""The ``grader`` command line: argument parsing and subcommand dispatch."""

import argparse
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass

from classroom_grader import GraderError, __version__, init, students


@dataclass(frozen=True)
class Command:
    """A ``grader`` subcommand: its name, help text, arguments and handler."""

    name: str
    help: str
    add_arguments: Callable[[argparse.ArgumentParser], None]
    run: Callable[[argparse.Namespace], int]


COMMANDS: tuple[Command, ...] = (
    Command("init", init.HELP, init.add_arguments, init.run),
    Command("students", students.HELP, students.add_arguments, students.run),
)


def build_parser() -> argparse.ArgumentParser:
    """Return the ``grader`` parser with one subparser per entry in ``COMMANDS``."""
    parser = argparse.ArgumentParser(
        prog="grader",
        description="Collect GitHub Classroom submissions and push grading feedback.",
    )
    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {__version__}"
    )
    subparsers = parser.add_subparsers(dest="command", metavar="COMMAND")
    for command in COMMANDS:
        subparser = subparsers.add_parser(
            command.name, help=command.help, description=command.help
        )
        command.add_arguments(subparser)
        subparser.set_defaults(run=command.run)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run ``grader`` with ``argv`` (default: ``sys.argv[1:]``); return the exit code.

    Without a subcommand, print the help text and return 2. A ``GraderError``
    or an ``OSError`` (such as a denied write) is printed without a traceback
    and returns 1.
    """
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help()
        return 2
    try:
        return args.run(args)
    except (GraderError, OSError) as exc:
        print(f"grader: {exc}", file=sys.stderr)
        return 1
