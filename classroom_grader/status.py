"""``grader status``: whether the grading feedback has reached GitHub."""

import argparse
import json
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from functools import partial
from pathlib import Path, PurePosixPath
from typing import Any

from classroom_grader.course import (
    add_repo_options,
    individual_assignments,
    map_in_parallel,
    open_course,
    submission_folder,
)
from classroom_grader.git import GitError, run_git
from classroom_grader.github import repo_url
from classroom_grader.repo import (
    clone_problem,
    commit,
    format_time,
    grader_identity,
    is_missing_repo,
    is_unfetched,
    late_commit,
    leads_outside,
    repo_name,
    upstream,
)
from classroom_grader.settings import Assignment, Settings
from classroom_grader.table import format_table, printable

HELP = "Show whether each student's feedback is committed and pushed."
STATES = (
    "up to date",
    "student pushed since",
    "feedback not committed",
    "not pushed",
    "diverged",
    "empty",
    "not fetched",
    "no repo",
    "refused",
    "failed",
)
# States in which feedback has not reached GitHub, or could not be checked.
UNFINISHED = {"feedback not committed", "not pushed", "diverged", "refused", "failed"}
NOISE_FOLDER = ".ipynb_checkpoints"
# Larger notebooks (in bytes) are not parsed to look for metadata-only changes.
NOTEBOOK_LIMIT = 20_000_000


@dataclass(frozen=True)
class RepoStatus:
    """One repository's state, its other local changes and a late commit time."""

    student: str
    state: str
    other_changes: tuple[str, ...] = ()
    late: datetime | None = None
    detail: str = ""


def add_arguments(parser: argparse.ArgumentParser) -> None:
    """Add the ``grader status`` arguments."""
    add_repo_options(parser)
    parser.add_argument(
        "--no-fetch",
        action="store_true",
        help="compare with what was fetched last instead of fetching first",
    )


def run(args: argparse.Namespace) -> int:
    """Print the state of every selected student's repository.

    Return 1 when any feedback is not committed or not pushed, or a repository
    could not be checked.
    """
    settings, students = open_course(args)
    assignments = individual_assignments(settings, args.assignments, "status")
    graders = grader_identity(settings.root)
    names = [student.username for student in students]
    unfinished = False
    for assignment in assignments:
        check = partial(
            repo_status, settings, assignment, graders=graders, fetch=not args.no_fetch
        )
        results = map_in_parallel(check, names, args.jobs)
        print(status_report(assignment, results))
        unfinished = unfinished or any(r.state in UNFINISHED for r in results)
    return 1 if unfinished else 0


def repo_status(
    settings: Settings,
    assignment: Assignment,
    name: str,
    *,
    graders: set[str],
    fetch: bool = True,
) -> RepoStatus:
    """Return the state of ``name``'s clone of ``assignment``, fetching it first.

    Without a local clone, the remote is asked whether the repository exists
    (unless ``fetch`` is false).
    """
    folder = submission_folder(settings, name, assignment)
    repo = repo_name(assignment, name)
    try:
        if (problem := leads_outside(settings, folder)) is not None:
            return RepoStatus(name, "refused", detail=problem)
        if is_unfetched(folder):
            if fetch:
                url = repo_url(settings.organization, repo, settings.protocol)
                run_git(["ls-remote", "--heads", url])
            return RepoStatus(name, "not fetched")
        if (problem := clone_problem(settings, folder, repo)) is not None:
            return RepoStatus(name, "refused", detail=problem)
        if fetch:
            run_git(["fetch", "--quiet", "origin"], folder)
        feedback_changed, other_changes = _local_changes(
            folder, settings.feedback_files
        )
        state = _sync_state(folder, feedback_changed)
        if state is None:
            return RepoStatus(
                name, "refused", detail="its checkout does not track a branch on origin"
            )
        late = late_commit(folder, assignment.deadline, graders)
    except GitError as error:
        if is_missing_repo(error):
            return RepoStatus(name, "no repo")
        return RepoStatus(name, "failed", detail=str(error))
    except (OSError, RuntimeError) as error:  # RuntimeError: a symlink loop on 3.11
        return RepoStatus(name, "failed", detail=str(error))
    return RepoStatus(name, state, other_changes, late)


def status_report(assignment: Assignment, results: list[RepoStatus]) -> str:
    """Return a table of the results, the problems found, and the counts."""
    deadline = assignment.deadline
    rows = [
        [
            r.student,
            r.state,
            ", ".join(r.other_changes) or "-",
            format_time(r.late, deadline) if r.late and deadline else "-",
        ]
        for r in results
    ]
    headers = ["Student", "State", "Other local changes", "Late"]
    lines = [assignment.name, format_table(headers, rows)]
    problems = [r for r in results if r.detail]
    if problems:
        lines.append("Refused or failed:")
        lines.extend(f"  {r.student}: {r.detail}" for r in problems)
    counts = Counter(r.state for r in results)
    summary = (
        ", ".join(f"{counts[s]} {s}" for s in STATES if counts[s]) or "no students"
    )
    lines.append(f"{assignment.name}: {summary}")
    return "\n".join(lines)


def _sync_state(folder: Path, feedback_changed: bool) -> str | None:
    """Compare the clone with its origin branch; None if it tracks no such branch."""
    head = commit(folder, "HEAD")
    tracked = upstream(folder)
    if feedback_changed:
        return "feedback not committed"
    if tracked is None:
        return "empty" if head is None else None
    if head is None:
        return "student pushed since"
    counts = run_git(
        ["rev-list", "--left-right", "--count", f"HEAD...{tracked}"], folder
    )
    ahead, behind = (int(count) for count in counts.split())
    if ahead and behind:
        return "diverged"
    if ahead:
        return "not pushed"
    return "student pushed since" if behind else "up to date"


def _local_changes(
    folder: Path, feedback_files: tuple[str, ...]
) -> tuple[bool, tuple[str, ...]]:
    """Return whether a feedback file changed, and the other changed files.

    A feedback file counts as changed also when it is new but ignored by the
    repository's .gitignore. Files in ``.ipynb_checkpoints`` folders are left
    out, and a notebook whose changes are all in metadata is marked "(metadata
    only)". A rename counts as a change of both paths.
    """
    feedback = set(feedback_files)
    entries = iter(
        run_git(
            ["status", "--porcelain=v1", "-z", "--untracked-files=all"], folder
        ).split("\0")
    )
    ignored = run_git(
        ["ls-files", "--others", "--ignored", "--exclude-standard", "--"]
        + [f":(literal){path}" for path in sorted(feedback)],
        folder,
    )
    feedback_changed = bool(ignored.strip())
    other: list[str] = []
    for entry in entries:
        if not entry:
            continue
        code, path = entry[:2], entry[3:]
        paths = [path]
        if "R" in code or "C" in code:  # the next entry is the path moved or copied
            source = next(entries, "")
            if "R" in code:
                paths.append(source)
        for changed in paths:
            if changed in feedback:
                feedback_changed = True
            elif NOISE_FOLDER in PurePosixPath(changed).parts:
                continue
            elif changed.endswith(".ipynb") and _metadata_only(folder, changed, code):
                other.append(f"{printable(changed)} (metadata only)")
            else:
                other.append(printable(changed))
    return feedback_changed, tuple(other)


def _metadata_only(folder: Path, path: str, code: str) -> bool:
    """Tell whether notebook ``path`` differs from HEAD only in metadata.

    ``code`` is the porcelain status: the staged version is compared when the
    first letter is M, the working copy when the second is. A version larger
    than ``NOTEBOOK_LIMIT`` makes the answer no.
    """
    if code not in (" M", "M ", "MM"):
        return False
    try:
        objects = [f"HEAD:{path}"] + ([f":0:{path}"] if code[0] == "M" else [])
        sizes = [int(run_git(["cat-file", "-s", name], folder)) for name in objects]
        if max(sizes) > NOTEBOOK_LIMIT:
            return False
        texts = [run_git(["show", name], folder) for name in objects]
        if code[1] == "M":
            with (folder / path).open("rb") as file:
                data = file.read(NOTEBOOK_LIMIT + 1)
            if len(data) > NOTEBOOK_LIMIT:
                return False
            texts.append(data.decode("utf-8"))
        committed, *changed = (_comparable(text) for text in texts)
        return all(version == committed for version in changed)
    except (GitError, OSError, ValueError, RecursionError):
        return False


def _comparable(text: str) -> str:
    """Return notebook JSON without metadata, as text that keeps JSON types apart."""
    return json.dumps(_without_metadata(json.loads(text)), sort_keys=True)


def _without_metadata(notebook: Any) -> Any:
    """Return a notebook without its own metadata and its cells' metadata."""
    if not isinstance(notebook, dict):
        return notebook
    rest = {key: value for key, value in notebook.items() if key != "metadata"}
    if isinstance(rest.get("cells"), list):
        rest["cells"] = [
            {key: value for key, value in cell.items() if key != "metadata"}
            if isinstance(cell, dict)
            else cell
            for cell in rest["cells"]
        ]
    return rest
