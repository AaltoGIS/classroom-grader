"""``grader template``: add the grading template to the end of the students' READMEs."""

import argparse
import re
from dataclasses import dataclass
from decimal import Decimal
from functools import partial
from pathlib import Path

from classroom_grader import GraderError, write_new
from classroom_grader.course import (
    add_repo_options,
    map_in_parallel,
    open_assignments,
    submission_folder,
)
from classroom_grader.git import GitError, run_git
from classroom_grader.repo import clone_problem, is_unfetched, leads_outside, repo_name
from classroom_grader.settings import (
    Assignment,
    GradingTemplate,
    Settings,
    template_heading,
)
from classroom_grader.table import state_counts

HELP = "Add the grading template to the end of each student's README."
STATES = ("added", "created", "already there", "not fetched", "refused", "failed")
# States listed by student under the counts.
_LISTED = ("not fetched", "refused", "failed")
_PLACEHOLDER = re.compile(r"\{(\w+)\}")


@dataclass(frozen=True)
class TemplateResult:
    """What adding the template to one student's README did."""

    student: str
    state: str
    detail: str = ""


def add_arguments(parser: argparse.ArgumentParser) -> None:
    """Add the ``grader template`` arguments."""
    add_repo_options(parser)


def run(args: argparse.Namespace) -> int:
    """Add the template to every selected student's README; 1 if any failed."""
    settings, selection = open_assignments(args)
    if missing := [
        assignment.name for assignment, _ in selection if not assignment.points
    ]:
        raise GraderError(
            f"no points in grader.toml for {', '.join(missing)}; add them to the "
            'assignment\'s table, such as points = { "Problem 1" = 8 }'
        )
    failed = False
    for assignment, names in selection:
        add_one = partial(add_template, settings, assignment)
        results = map_in_parallel(add_one, names, args.jobs)
        print(template_report(assignment, results))
        failed = failed or any(r.state in ("refused", "failed") for r in results)
    return 1 if failed else 0


def add_template(
    settings: Settings, assignment: Assignment, name: str
) -> TemplateResult:
    """Append the grading template to ``name``'s first feedback file.

    A file that already has the template's first line is left alone, and a
    missing one is created. The template takes the file's line endings.
    """
    folder = submission_folder(settings, name, assignment)
    path = folder / settings.feedback_files[0]
    try:
        if (problem := leads_outside(folder, settings.root / "submitted")) is not None:
            return TemplateResult(name, "refused", problem)
        if is_unfetched(folder):
            return TemplateResult(name, "not fetched")
        repo = repo_name(assignment, name)
        if (problem := clone_problem(folder, settings.organization, repo)) is not None:
            return TemplateResult(name, "refused", problem)
        if link := _first_link(folder, settings.feedback_files[0]):
            return TemplateResult(name, "refused", f"{link} is a symbolic link")
        template = grading_template(settings, assignment)
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            write_new(path, template.encode())
            return TemplateResult(name, "created")
        old = path.read_bytes()
        if template_heading(settings.grading_template.text) in _lines(old):
            return TemplateResult(name, "already there")
        gap = "" if not old else "\n" if old.endswith(b"\n") else "\n\n"
        newline = "\r\n" if b"\r\n" in old else "\n"
        added = (gap + template.replace("\r\n", "\n")).replace("\n", newline)
        with path.open("ab") as file:
            file.write(added.encode())
    except (GitError, OSError, GraderError) as error:
        return TemplateResult(name, "failed", str(error))
    except RuntimeError as error:  # a symlink loop on 3.11
        return TemplateResult(name, "failed", str(error))
    return TemplateResult(name, "added")


def _first_link(folder: Path, path: str) -> str | None:
    """Return the first part of ``path`` in ``folder`` that is a link, if any."""
    parts = path.split("/")
    for count in range(1, len(parts) + 1):
        if folder.joinpath(*parts[:count]).is_symlink():
            return "/".join(parts[:count])
    return None


def template_report(assignment: Assignment, results: list[TemplateResult]) -> str:
    """Return the counts of one assignment, and the students that need a look."""
    summary = state_counts(STATES, [r.state for r in results])
    lines = [f"{assignment.name}: {summary}"]
    lines.extend(
        f"  {r.student}: {r.state}{': ' + r.detail if r.detail else ''}"
        for r in results
        if r.state in _LISTED
    )
    return "\n".join(lines)


def grading_template(settings: Settings, assignment: Assignment) -> str:
    """Return the assignment's grading template, ending with a line break."""
    layout = settings.grading_template
    problems = "\n".join(
        _problem_line(layout, name, points)
        for name, points in assignment.points.items()
    )
    text = _fill(layout.text, _template_values(layout, assignment, problems))
    return text if text.endswith("\n") else text + "\n"


def unfilled_points(
    settings: Settings, assignment: Assignment, text: str | None
) -> list[str]:
    """Return the problems, and ``total``, still without points in a template.

    ``text`` is a feedback file's text; a problem or total line is unfilled
    while ``text`` holds it exactly as ``grader template`` wrote it.
    """
    if not assignment.points or text is None:
        return []
    present = {line.strip() for line in text.splitlines()}
    layout = settings.grading_template
    missing = [
        name
        for name, points in assignment.points.items()
        if _problem_line(layout, name, points).strip() in present
    ]
    values = _template_values(layout, assignment, "")
    totals = {
        _fill(line, values).strip()
        for line in layout.text.splitlines()
        if "{total}" in line
    }
    if totals & present:
        missing.append("total")
    return missing


def template_text(
    settings: Settings, folder: Path, revision: str | None = None
) -> str | None:
    """Return the text of the clone's first feedback file, the one with the template.

    With ``revision``, the file as committed there. None when there is no such
    file, or a link on disk leads to it.
    """
    path = settings.feedback_files[0]
    if revision is not None:
        tree = run_git(["ls-tree", "-r", "--name-only", "-z", revision], folder)
        if path not in tree.split("\0"):
            return None
        return run_git(["cat-file", "blob", f"{revision}:{path}"], folder)
    file = folder / path
    if _first_link(folder, path) or not file.is_file():
        return None
    return file.read_bytes().decode("utf-8", "replace")


def _problem_line(layout: GradingTemplate, name: str, points: int | float) -> str:
    """Return the template's line for one problem and its maximum points."""
    return _fill(layout.problem, {"name": name, "points": _number(points)})


def _template_values(
    layout: GradingTemplate, assignment: Assignment, problems: str
) -> dict[str, str]:
    """Return what the template text's placeholders stand for."""
    return {
        "problems": problems,
        "total": _number(sum(map(_decimal, assignment.points.values()))),
        "comment": assignment.comment or layout.comment,
    }


def _fill(text: str, values: dict[str, str]) -> str:
    """Replace the ``{name}`` placeholders of ``values`` in ``text``; keep others."""
    return _PLACEHOLDER.sub(lambda match: values.get(match[1], match[0]), text)


def _decimal(value: int | float) -> Decimal:
    """Return points as the decimal number written in ``grader.toml``."""
    return Decimal(value if isinstance(value, int) else repr(value))


def _number(value: int | float | Decimal) -> str:
    """Return points as written by hand: ``8``, ``7.5``, never rounded."""
    number = _decimal(value) if not isinstance(value, Decimal) else value
    if number == number.to_integral_value():
        return str(int(number))
    return format(number.normalize(), "f")


def _lines(data: bytes) -> set[str]:
    """Return the lines of a file's contents, without surrounding spaces."""
    return {line.strip() for line in data.decode("utf-8", "replace").splitlines()}
