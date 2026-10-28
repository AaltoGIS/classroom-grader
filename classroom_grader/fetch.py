"""``grader fetch``: clone or update the students' repositories in ``submitted/``."""

import argparse
import contextlib
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from functools import partial
from pathlib import Path

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

HELP = "Clone or update the students' repositories of the given assignments."
STATES = (
    "cloned",
    "updated",
    "up to date",
    "empty",
    "not updated",
    "refused",
    "no repo",
    "failed",
)
_LISTED = {
    "empty": "Empty repository (nothing pushed yet)",
    "not updated": "Not updated (fetched only)",
    "refused": "Refused",
    "no repo": "No repo (not accepted, or no access)",
    "failed": "Failed",
}


@dataclass(frozen=True)
class FetchResult:
    """One repository's fetch outcome; ``late`` is a commit time after the deadline."""

    student: str
    state: str
    detail: str = ""
    late: datetime | None = None


def add_arguments(parser: argparse.ArgumentParser) -> None:
    """Add the ``grader fetch`` arguments."""
    add_repo_options(parser)


def run(args: argparse.Namespace) -> int:
    """Fetch the selected students' repositories; 1 if any was refused or failed."""
    settings, students = open_course(args)
    assignments = individual_assignments(settings, args.assignments, "fetch")
    graders = grader_identity(settings.root)
    names = [student.username for student in students]
    failed = False
    for assignment in assignments:
        fetch_one = partial(fetch_repo, settings, assignment, graders=graders)
        results = map_in_parallel(fetch_one, names, args.jobs)
        print(fetch_report(assignment, results))
        failed = failed or any(r.state in ("refused", "failed") for r in results)
    return 1 if failed else 0


def fetch_repo(
    settings: Settings, assignment: Assignment, name: str, *, graders: set[str]
) -> FetchResult:
    """Clone or update ``name``'s repository of ``assignment`` into its nbgrader folder.

    A clean clone without local commits is fast-forwarded; one with local changes
    or commits is only fetched. A folder that is not a clone of the expected
    repository, or that leads outside ``submitted/``, is left alone.
    """
    folder = submission_folder(settings, name, assignment)
    repo = repo_name(assignment, name)
    try:
        if (problem := leads_outside(settings, folder)) is not None:
            return FetchResult(name, "refused", problem)
        if is_unfetched(folder):
            _clone(repo_url(settings.organization, repo, settings.protocol), folder)
            state, detail = ("cloned" if upstream(folder) else "empty"), ""
        elif (problem := clone_problem(settings, folder, repo)) is not None:
            return FetchResult(name, "refused", problem)
        else:
            state, detail = _update(folder)
        late = (
            None
            if state == "empty"
            else late_commit(folder, assignment.deadline, graders)
        )
    except GitError as error:
        if is_missing_repo(error):
            return FetchResult(name, "no repo")
        return FetchResult(name, "failed", str(error))
    except (OSError, RuntimeError) as error:  # RuntimeError: a symlink loop on 3.11
        return FetchResult(name, "failed", str(error))
    return FetchResult(name, state, detail, late)


def fetch_report(assignment: Assignment, results: list[FetchResult]) -> str:
    """Summarise the results of one assignment, listing what needs attention."""
    counts = Counter(result.state for result in results)
    summary = (
        ", ".join(f"{counts[s]} {s}" for s in STATES if counts[s]) or "no students"
    )
    lines = [f"{assignment.name}: {summary}"]
    for state, title in _LISTED.items():
        listed = [result for result in results if result.state == state]
        if listed:
            lines.append(f"{title}:")
            lines.extend(
                f"  {r.student}{': ' + r.detail if r.detail else ''}" for r in listed
            )
    late = [result for result in results if result.late]
    if late:
        deadline = assignment.deadline
        lines.append(
            f"Newest commit after the deadline {format_time(deadline, deadline)} "
            "(commit times come from the students' computers):"
        )
        lines.extend(f"  {r.student}: {format_time(r.late, deadline)}" for r in late)
    return "\n".join(lines)


def _clone(url: str, folder: Path) -> None:
    """Clone ``url`` into ``folder``; on failure, remove a student folder it made."""
    created = not folder.parent.exists()
    folder.parent.mkdir(parents=True, exist_ok=True)
    try:
        run_git(["clone", "--quiet", url, str(folder)])
    except (GitError, OSError):
        if created:
            with contextlib.suppress(OSError):
                folder.parent.rmdir()
        raise


def _update(folder: Path) -> tuple[str, str]:
    """Fetch ``folder`` and fast-forward it unless it has local changes or commits."""
    run_git(["fetch", "--quiet", "origin"], folder)
    before = commit(folder, "HEAD")
    tracked = upstream(folder)
    if tracked is None:
        if before is None:
            return "empty", ""
        return "not updated", "its checkout does not track a branch on origin"
    changed = bool(run_git(["status", "--porcelain", "--untracked-files=no"], folder))
    ahead = 0
    if before is not None:
        ahead = int(run_git(["rev-list", "--count", f"{tracked}..HEAD"], folder))
    if changed or ahead:
        reasons = ["local changes"] if changed else []
        if ahead:
            reasons.append(f"{ahead} local commit{'s' if ahead > 1 else ''}")
        return "not updated", " and ".join(reasons)
    run_git(["merge", "--ff-only", "--quiet", tracked], folder)
    return ("updated" if commit(folder, "HEAD") != before else "up to date"), ""
