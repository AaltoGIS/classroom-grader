"""``grader push``: commit the feedback files and push them to GitHub."""

import argparse
import os
from dataclasses import dataclass, replace
from functools import partial
from pathlib import Path

from classroom_grader import GraderError
from classroom_grader.course import (
    add_repo_options,
    map_in_parallel,
    open_assignments,
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
from classroom_grader.settings import Assignment, Settings, repository_paths
from classroom_grader.table import format_table, printable, state_counts
from classroom_grader.template import template_text, unfilled_points

HELP = "Commit the feedback files and push them to the students' repositories."
DEFAULT_MESSAGE = "Add grading"
STATES = (
    "pushed",
    "would push",
    "nothing to push",
    "template not filled",
    "not fetched",
    "blocked",
    "conflict",
    "refused",
    "failed",
)
# git's options for a list of changed paths, NUL-separated and unquoted.
_NAMES = ("--name-only", "--no-renames", "-z")
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
    parser.add_argument(
        "--extra-file",
        action="append",
        metavar="PATH",
        help="also commit and push this file, and earlier commits that change it; "
        "repeat for more",
    )


def run(args: argparse.Namespace) -> int:
    """Push every selected student's feedback; return 1 if any needs attention.

    ``--extra-file`` paths count as feedback files for this run.
    """
    path_problems: list[str] = []
    extra = repository_paths(args.extra_file or [], "--extra-file", path_problems)
    if path_problems:
        raise GraderError("; ".join(path_problems))
    settings, selection = open_assignments(args)
    feedback = tuple(dict.fromkeys((*settings.feedback_files, *extra)))
    settings = replace(settings, feedback_files=feedback)
    problems = False
    for assignment, names in selection:
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
    are. Earlier local commits that change any other file are not pushed
    ("refused"), and neither is a grading template still without points
    ("template not filled"). When the student pushed since, the commits are
    rebased onto the student's, unless other local changes touch the same
    files ("blocked"); a rebase conflict is aborted ("conflict"), keeping the
    local commits.
    """
    folder = submission_folder(settings, name, assignment)
    repo = repo_name(assignment, name)
    try:
        if (problem := leads_outside(folder, settings.root / "submitted")) is not None:
            return PushResult(name, "refused", problem)
        if is_unfetched(folder):
            return PushResult(name, "not fetched")
        if (problem := clone_problem(folder, settings.organization, repo)) is not None:
            return PushResult(name, "refused", problem)
        run_git(["fetch", "--quiet", "origin"], folder)
        tracked = upstream(folder)
        fetched = commit(folder, tracked) if tracked else None
        if commit(folder, "HEAD") is None or tracked is None or fetched is None:
            return PushResult(
                name, "refused", "its checkout has no commit on a branch of origin"
            )
        feedback_changed = local_changes(folder, settings.feedback_files)[0]
        ahead, behind = ahead_behind(folder, fetched)
        if not feedback_changed and not ahead:
            return PushResult(name, "nothing to push")
        if result := _unfilled(
            settings, assignment, name, template_text(settings, folder)
        ):
            return result
        if ahead and (refusal := _other_files(folder, fetched, "HEAD", settings)):
            return PushResult(name, "refused", refusal)
        if behind and (reason := _rebase_blocker(folder, fetched, settings)):
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
        if behind and not _rebase(folder, fetched):
            return PushResult(
                name,
                "conflict",
                "the student's new commits conflict with yours; the rebase was "
                "undone, so pull and resolve by hand",
            )
        tip = run_git(["rev-parse", "--verify", "HEAD"], folder).strip()
        if refusal := _other_files(folder, fetched, tip, settings):
            return PushResult(name, "refused", refusal)
        if result := _unfilled(
            settings, assignment, name, template_text(settings, folder, tip)
        ):
            return result
        branch = f"refs/heads/{tracked.removeprefix('refs/remotes/origin/')}"
        # The lease refuses the push if the branch has moved since the fetch.
        lease = f"--force-with-lease={branch}:{fetched}"
        run_git(["push", "--quiet", lease, "origin", f"{tip}:{branch}"], folder)
    except GitError as error:
        return PushResult(name, "failed", str(error))
    except (OSError, RuntimeError) as error:  # RuntimeError: a symlink loop on 3.11
        return PushResult(name, "failed", str(error))
    return PushResult(name, "pushed", ", ".join(steps))


def push_report(assignment: Assignment, results: list[PushResult]) -> str:
    """Return a table of what was pushed per student, and the counts."""
    rows = [[r.student, r.state, r.detail or "-"] for r in results]
    summary = state_counts(STATES, [r.state for r in results])
    table = format_table([assignment.owner_title, "Result", "Details"], rows)
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


def _unfilled(
    settings: Settings, assignment: Assignment, name: str, text: str | None
) -> PushResult | None:
    """Return the "template not filled" result when ``text`` lacks points."""
    if missing := unfilled_points(settings, assignment, text):
        return PushResult(
            name, "template not filled", f"no points for {', '.join(missing)}"
        )
    return None


def _other_files(
    folder: Path, fetched: str, tip: str, settings: Settings
) -> str | None:
    """Say which non-feedback files pushing ``tip`` would change; None if none.

    Every commit after ``fetched`` counts with the files it changes, a merge
    only with those it changes from every parent; and the whole range counts
    with what ``tip`` changes from the last commit it shares with ``fetched``.
    So merging the student's commits in adds none of their files, but undoing
    one of their changes does.
    """
    base = run_git(["merge-base", tip, fetched], folder).strip()
    paths = _paths(run_git(["diff", *_NAMES, base, tip], folder))
    for sha in run_git(["rev-list", f"{fetched}..{tip}"], folder).split():
        diff_tree = ["diff-tree", "-r", "--root", "--cc", "--no-commit-id"]
        paths |= _paths(run_git([*diff_tree, *_NAMES, sha], folder))
    others = sorted(paths - set(settings.feedback_files))
    if not others:
        return None
    shown = ", ".join(printable(path) for path in others)
    return (
        f"your commits also change {shown}; to push them, name each with "
        f"--extra-file, or undo the commits with git reset {base[:7]}, which keeps "
        "their changes in your files"
    )


def _paths(names: str) -> set[str]:
    """Return the paths in git's ``--name-only -z`` output."""
    return set(names.split("\0")) - {""}


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
