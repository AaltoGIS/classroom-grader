"""``grader push``: commit the feedback files and push them to GitHub."""

import argparse
import os
from collections import Counter
from dataclasses import dataclass
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
from classroom_grader.repo import (
    ahead_behind,
    clone_problem,
    commit,
    is_unfetched,
    leads_outside,
    literal_pathspecs,
    local_changes,
    repo_name,
    upstream,
)
from classroom_grader.settings import Assignment, Settings
from classroom_grader.table import format_table, printable

HELP = "Commit the feedback files and push them to the students' repositories."
DEFAULT_MESSAGE = "Add grading"
STATES = (
    "pushed",
    "would push",
    "nothing to push",
    "not fetched",
    "blocked",
    "conflict",
    "refused",
    "failed",
)
# States that leave feedback unpushed and need the grader's attention.
PROBLEMS = {"blocked", "conflict", "refused", "failed"}


@dataclass(frozen=True)
class PushResult:
    """What pushing one repository did, or would do with ``--dry-run``."""

    student: str
    state: str
    detail: str = ""


def add_arguments(parser: argparse.ArgumentParser) -> None:
    """Add the ``grader push`` arguments."""
    add_repo_options(parser)
    parser.add_argument(
        "-m",
        "--message",
        default=DEFAULT_MESSAGE,
        help=f'commit message (default: "{DEFAULT_MESSAGE}")',
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="fetch and show what would be committed and pushed, changing nothing else",
    )


def run(args: argparse.Namespace) -> int:
    """Push every selected student's feedback; return 1 if any needs attention."""
    settings, students = open_course(args)
    assignments = individual_assignments(settings, args.assignments, "push")
    names = [student.username for student in students]
    problems = False
    for assignment in assignments:
        push_one = partial(
            push_repo, settings, assignment, message=args.message, dry_run=args.dry_run
        )
        results = map_in_parallel(push_one, names, args.jobs)
        print(push_report(assignment, results))
        problems = problems or any(r.state in PROBLEMS for r in results)
    return 1 if problems else 0


def push_repo(
    settings: Settings,
    assignment: Assignment,
    name: str,
    *,
    message: str,
    dry_run: bool = False,
) -> PushResult:
    """Commit ``name``'s changed feedback files and push them with any local commits.

    Only the feedback files are committed; other local changes stay as they
    are. When the student pushed since, the commits are rebased onto the
    student's, unless other local changes touch the same files ("blocked"); a
    rebase conflict is aborted ("conflict"), keeping the local commits.
    """
    folder = submission_folder(settings, name, assignment)
    repo = repo_name(assignment, name)
    try:
        if (problem := leads_outside(settings, folder)) is not None:
            return PushResult(name, "refused", problem)
        if is_unfetched(folder):
            return PushResult(name, "not fetched")
        if (problem := clone_problem(settings, folder, repo)) is not None:
            return PushResult(name, "refused", problem)
        run_git(["fetch", "--quiet", "origin"], folder)
        tracked = upstream(folder)
        if commit(folder, "HEAD") is None or tracked is None:
            return PushResult(
                name, "refused", "its checkout has no commit on a branch of origin"
            )
        feedback_changed = local_changes(folder, settings.feedback_files)[0]
        ahead, behind = ahead_behind(folder, tracked)
        if not feedback_changed and not ahead:
            return PushResult(name, "nothing to push")
        if behind and (reason := _rebase_blocker(folder, tracked, settings)):
            return PushResult(name, "blocked", reason)
        steps = ["commit feedback"] if feedback_changed else []
        if behind:
            steps.append(f"rebase onto {_commit_count(behind)} by the student")
        steps.append(f"push {_commit_count(ahead + feedback_changed)}")
        if dry_run:
            return PushResult(name, "would push", ", ".join(steps))
        if feedback_changed and not _commit_feedback(
            folder, settings.feedback_files, message
        ):
            return PushResult(name, "failed", "found no feedback file to commit")
        if behind and not _rebase(folder, tracked):
            return PushResult(
                name,
                "conflict",
                "the student's new commits conflict with yours; the rebase was "
                "undone, so pull and resolve by hand",
            )
        branch = tracked.removeprefix("refs/remotes/origin/")
        run_git(["push", "--quiet", "origin", f"HEAD:refs/heads/{branch}"], folder)
    except GitError as error:
        return PushResult(name, "failed", str(error))
    except (OSError, RuntimeError) as error:  # RuntimeError: a symlink loop on 3.11
        return PushResult(name, "failed", str(error))
    return PushResult(name, "pushed", ", ".join(steps))


def push_report(assignment: Assignment, results: list[PushResult]) -> str:
    """Return a table of what was pushed per student, and the counts."""
    rows = [[r.student, r.state, r.detail or "-"] for r in results]
    counts = Counter(r.state for r in results)
    summary = (
        ", ".join(f"{counts[s]} {s}" for s in STATES if counts[s]) or "no students"
    )
    table = format_table(["Student", "Result", "Details"], rows)
    return f"{assignment.name}\n{table}\n{assignment.name}: {summary}"


def _commit_feedback(
    folder: Path, feedback_files: tuple[str, ...], message: str
) -> bool:
    """Commit the feedback files, and nothing else.

    Files on disk or in the index are added first (``--force`` adds one that
    .gitignore ignores); a file that is only in HEAD is committed as deleted.
    Return False, without running git, when there is no feedback file at all:
    git add and git commit without paths would take every change.
    """
    pathspecs = literal_pathspecs(feedback_files)
    index = set(run_git(["ls-files", "-z", "--", *pathspecs], folder).split("\0"))
    head = run_git(["ls-tree", "-r", "--name-only", "-z", "HEAD"], folder)
    on_disk = {p for p in feedback_files if p in index or os.path.lexists(folder / p)}
    paths = [p for p in feedback_files if p in on_disk or p in head.split("\0")]
    if not paths:
        return False
    if on_disk:
        run_git(
            ["add", "--all", "--force", "--", *literal_pathspecs(sorted(on_disk))],
            folder,
        )
    run_git(
        ["commit", "--quiet", "--message", message, "--", *literal_pathspecs(paths)],
        folder,
    )
    return True


def _rebase_blocker(folder: Path, tracked: str, settings: Settings) -> str | None:
    """Say why rebasing onto the student's new commits could harm local changes.

    The rebase's autostash brings staged changes back unstaged, and cannot
    keep a local change to a path that the student's commits also change.
    """
    feedback = {*settings.feedback_files, ""}
    staged = run_git(["diff", "--cached", "--name-only", "--no-renames", "-z"], folder)
    if staged_others := sorted(set(staged.split("\0")) - feedback):
        shown = ", ".join(printable(path) for path in staged_others)
        return (
            f"rebasing onto the student's new commits would unstage your staged "
            f"changes to {shown}; commit or unstage them first"
        )
    if overlap := _overlap(folder, tracked, settings.feedback_files):
        shown = ", ".join(printable(path) for path in overlap)
        return (
            f"the student's new commits also change {shown}, which you changed "
            "locally; commit, discard or stash those changes first"
        )
    return None


def _overlap(folder: Path, tracked: str, feedback_files: tuple[str, ...]) -> list[str]:
    """Return the local non-feedback paths that new student commits would touch.

    Local paths are changed tracked files and all untracked files, ignored ones
    too (a rebase overwrites those without asking). A path overlaps when the
    student changed it, a folder holding it, or a file inside it, ignoring case
    as the Windows and macOS file systems do.
    """
    diff = ["diff", "--name-only", "--no-renames", "-z"]
    local = set(run_git([*diff, "HEAD"], folder).split("\0"))
    local |= set(run_git(["ls-files", "--others", "-z"], folder).split("\0"))
    local -= {*feedback_files, ""}
    student = set(run_git([*diff, f"HEAD...{tracked}"], folder).split("\0")) - {""}
    return sorted(path for path in local if any(_nested(path, s) for s in student))


def _nested(path: str, other: str) -> bool:
    """Tell whether two repository paths are the same or one holds the other."""
    path, other = path.casefold(), other.casefold()
    return path == other or path.startswith(f"{other}/") or other.startswith(f"{path}/")


def _rebase(folder: Path, tracked: str) -> bool:
    """Rebase onto ``tracked``, keeping other local changes; undo it on a conflict."""
    try:
        run_git(["rebase", "--quiet", "--autostash", tracked], folder)
    except GitError:
        run_git(["rebase", "--abort"], folder)
        return False
    return True


def _commit_count(count: int) -> str:
    """Return "1 commit" or "<count> commits"."""
    return f"{count} commit{'' if count == 1 else 's'}"
