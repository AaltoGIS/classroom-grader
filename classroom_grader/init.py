"""``grader init``: write ``grader.toml``, ``nbgrader_config.py`` and ``.gitignore``."""

import argparse
import json
import os
import re
from pathlib import Path

from classroom_grader import GraderError
from classroom_grader.settings import SETTINGS_FILE, Settings, parse_settings

HELP = "Write grader.toml, nbgrader_config.py and .gitignore for a course."
DEFAULT_ROSTER = "student_info.csv"
GITIGNORE = ".gitignore"
# Filled on each computer by grader and nbgrader; never part of the course repository.
GITIGNORE_LINES = (
    "submitted/",
    "source/",
    "release/",
    "autograded/",
    "feedback/",
    "gradebook.db",
)
NBGRADER_CONFIG = "nbgrader_config.py"
NBGRADER_CONFIG_TEXT = '''\
"""nbgrader settings for the course, written by grader init."""

import os

c = get_config()  # noqa: F821

c.CourseDirectory.root = os.path.dirname(os.path.abspath(__file__))
c.CourseDirectory.course_id = {course_id}
'''

_BARE_TOML_KEY = re.compile(r"[A-Za-z0-9_-]+")


def add_arguments(parser: argparse.ArgumentParser) -> None:
    """Add the ``grader init`` options; values left out are asked for."""
    parser.add_argument(
        "--course",
        type=Path,
        default=Path("."),
        help="course folder (default: the current folder)",
    )
    parser.add_argument("--organization", help="GitHub organization of the course")
    parser.add_argument(
        "--classroom",
        help="Classroom 50 classroom, the start of the students' repository names",
    )
    parser.add_argument(
        "--roster",
        help="roster CSV file, relative to the course folder "
        f"(default: {DEFAULT_ROSTER})",
    )
    parser.add_argument(
        "--assignment",
        action="append",
        metavar="NAME",
        help="assignment folder name, such as Exercise-1; repeat for more",
    )


def run(args: argparse.Namespace) -> int:
    """Write the course settings, asking for the values not given as options.

    An existing ``nbgrader_config.py`` is replaced only after confirmation and
    kept as ``nbgrader_config.py.bak``; an existing ``.gitignore`` gets the
    lines it lacks.
    """
    root = args.course.resolve()
    if not root.is_dir():
        raise GraderError(f"{root} is not a folder")
    settings_path = root / SETTINGS_FILE
    if os.path.lexists(settings_path):
        raise GraderError(f"{settings_path} exists already; edit it instead")
    organization = args.organization or _ask("GitHub organization")
    classroom = args.classroom or _ask("Classroom 50 classroom")
    roster = args.roster or _ask("Roster CSV file", DEFAULT_ROSTER)
    names = args.assignment
    if names is None:
        names = (_ask("Assignment folder names, separated by commas") or "").split(",")
    data = {
        "organization": organization,
        "roster": roster,
        "assignments": {name.strip(): {} for name in names if name.strip()},
    }
    if classroom:
        data["classroom"] = classroom
    settings = parse_settings(data, root)

    config_path = root / NBGRADER_CONFIG
    backup = config_path.with_name(NBGRADER_CONFIG + ".bak")
    config_text = NBGRADER_CONFIG_TEXT.format(course_id=json.dumps(organization))
    if os.path.lexists(config_path) and not config_path.is_file():
        raise GraderError(f"{config_path} is not a file; move it away first")
    old_bytes = config_path.read_bytes() if config_path.is_file() else None
    old_text = None
    if old_bytes is not None:
        old_text = old_bytes.decode("utf-8", "replace").replace("\r\n", "\n")
    replace = (
        old_text is not None
        and old_text != config_text
        and _confirm(
            f"{config_path} exists. Replace it and keep the old one as {backup.name}?"
        )
    )
    if replace and os.path.lexists(backup):
        raise GraderError(f"{backup} exists already; move it away first")
    gitignore = root / GITIGNORE
    if os.path.lexists(gitignore) and not gitignore.is_file():
        raise GraderError(f"{gitignore} is not a file; move it away first")
    old_gitignore = gitignore.read_bytes() if gitignore.is_file() else None

    _write_new(settings_path, _settings_text(settings, roster).encode())
    print(f"Wrote {settings_path}")
    if replace:
        _write_new(backup, old_bytes)
        config_path.unlink()
        print(f"Kept the old {NBGRADER_CONFIG} as {backup}")
    if old_text is None or replace:
        _write_new(config_path, config_text.encode())
        print(f"Wrote {config_path}")
    elif old_text != config_text:
        print(f"Left {config_path} unchanged")
    _update_gitignore(gitignore, old_gitignore)
    return 0


def _update_gitignore(path: Path, old: bytes | None) -> None:
    """Write ``.gitignore``, or append the ``GITIGNORE_LINES`` that ``old`` lacks."""
    present = set()
    if old is not None:
        present = {line.strip() for line in old.decode("utf-8", "replace").splitlines()}
    missing = [line for line in GITIGNORE_LINES if line not in present]
    if not missing:
        print(f"Left {path} unchanged")
        return
    text = "\n".join(missing) + "\n"
    if old is None:
        _write_new(path, text.encode())
        print(f"Wrote {path}")
        return
    if old and not old.endswith(b"\n"):
        text = "\n" + text
    with path.open("ab") as file:
        file.write(text.encode())
    print(f"Added {', '.join(missing)} to {path}")


def _write_new(path: Path, content: bytes) -> None:
    """Write ``content`` to a new file; refuse when ``path`` exists, even as a link."""
    try:
        with path.open("xb") as file:
            file.write(content)
    except FileExistsError:
        raise GraderError(f"{path} exists already") from None


def _ask(question: str, default: str | None = None) -> str | None:
    """Ask on the terminal; return ``default`` for an empty answer or no input."""
    prompt = f"{question} [{default}]: " if default else f"{question}: "
    try:
        answer = input(prompt).strip()
    except EOFError:
        answer = ""
    return answer or default


def _confirm(question: str) -> bool:
    """Ask a yes/no question; anything but yes, or no input, means no."""
    return (_ask(f"{question} [y/N]") or "").lower() in ("y", "yes")


def _settings_text(settings: Settings, roster: str) -> str:
    """Render ``grader.toml``, with the optional settings as comments."""
    classroom = '# classroom = "NAME"  # Classroom 50 classroom'
    if settings.classroom:
        classroom = f"classroom = {_toml_string(settings.classroom)}"
    lines = [
        f"organization = {_toml_string(settings.organization)}",
        classroom,
        f"roster = {_toml_string(roster)}",
        '# username_column = "user"  # found in the roster when left out',
        '# grader = "NAME"  # default for --grader',
        'feedback_files = ["README.md"]',
        '# protocol = "ssh"  # for new clones; the default is "https"',
    ]
    for assignment in settings.assignments.values():
        lines += [
            "",
            f"[assignments.{_toml_key(assignment.name)}]",
            f"# repo_prefix = {_toml_string(assignment.repo_prefix)}  # the default",
            f"# source_repo = {_toml_string(assignment.source_repo)}  # the default",
            "# deadline = 2026-12-31T23:59:00+02:00",
        ]
    return "\n".join(lines) + "\n"


def _toml_string(value: str) -> str:
    """Quote ``value`` as a TOML basic string."""
    return json.dumps(value, ensure_ascii=False).replace("\x7f", "\\u007f")


def _toml_key(name: str) -> str:
    """Return ``name`` as a TOML key, quoted when it is not a bare key."""
    return name if _BARE_TOML_KEY.fullmatch(name) else _toml_string(name)
