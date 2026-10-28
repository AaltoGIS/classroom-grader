"""``grader fetch``: clone or update the students' repositories in ``submitted/``."""

import argparse
import contextlib
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime
from itertools import repeat
from pathlib import Path

from classroom_grader import GraderError
from classroom_grader.course import (
    add_course_options,
    open_course,
    select_assignments,
    submission_folder,
)
from classroom_grader.git import GitError, run_git
from classroom_grader.github import is_repo_url, repo_url, without_credentials
from classroom_grader.settings import Assignment, Settings

HELP = "Clone or update the students' repositories of the given assignments."
CLASSROOM_BOT = "github-classroom[bot]"
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
# Parts of git's messages for a repository that is missing or not visible: from
# GitHub over HTTPS or SSH, and for a local path.
_MISSING_REPO = (
    "repository not found",
    "does not exist",
    "does not appear to be a git repository",
)
# Commits searched, newest first, for the newest student commit.
_LOG_LIMIT = 1000
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
    parser.add_argument(
        "assignments", nargs="+", metavar="ASSIGNMENT", help="assignment in grader.toml"
    )
    add_course_options(parser)
    parser.add_argument(
        "--jobs",
        type=_positive_int,
        default=8,
        help="repositories handled at the same time (default: 8)",
    )


def run(args: argparse.Namespace) -> int:
    """Fetch the selected students' repositories; 1 if any was refused or failed."""
    settings, students = open_course(args)
    assignments = select_assignments(settings, args.assignments)
    for assignment in assignments:
        if assignment.type == "group":
            raise GraderError(
                f"{assignment.name} is a group assignment; grader fetch does not "
                "handle team repositories yet"
            )
    graders = _grader_identity(settings.root)
    failed = False
    for assignment in assignments:
        names = [student.username for student in students]
        with ThreadPoolExecutor(max_workers=args.jobs) as pool:
            results = list(
                pool.map(
                    fetch_repo,
                    repeat(settings),
                    repeat(assignment),
                    names,
                    repeat(graders),
                )
            )
        print(fetch_report(assignment, results))
        failed = failed or any(r.state in ("refused", "failed") for r in results)
    return 1 if failed else 0


def fetch_repo(
    settings: Settings, assignment: Assignment, name: str, graders: set[str]
) -> FetchResult:
    """Clone or update ``name``'s repository of ``assignment`` into its nbgrader folder.

    A clean clone without local commits is fast-forwarded; one with local changes
    or commits is only fetched. A folder that is not a clone of the expected
    repository, or that leads outside ``submitted/``, is left alone.
    """
    folder = submission_folder(settings, name, assignment)
    repo = f"{assignment.repo_prefix}-{name}"
    try:
        submitted = (settings.root / "submitted").resolve()
        if not folder.resolve().is_relative_to(submitted):
            return FetchResult(name, "refused", f"the folder leads outside {submitted}")
        if not folder.exists() or (folder.is_dir() and not any(folder.iterdir())):
            _clone(repo_url(settings.organization, repo, settings.protocol), folder)
            state, detail = ("cloned" if _upstream(folder) else "empty"), ""
        elif (problem := _clone_problem(settings, folder, repo)) is not None:
            return FetchResult(name, "refused", problem)
        else:
            state, detail = _update(folder)
        late = (
            None
            if state == "empty"
            else _late_commit(folder, assignment.deadline, graders)
        )
    except GitError as error:
        if any(text in error.stderr.lower() for text in _MISSING_REPO):
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
            f"Newest commit after the deadline {_time(deadline, deadline)} "
            "(commit times come from the students' computers):"
        )
        lines.extend(f"  {r.student}: {_time(r.late, deadline)}" for r in late)
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


def _clone_problem(settings: Settings, folder: Path, repo: str) -> str | None:
    """Say why ``folder`` is not a clone of the expected repository, if it is not."""
    git_folder = folder / ".git"
    if git_folder.is_symlink() or not git_folder.is_dir():
        return "the folder exists but has no .git folder of its own"
    if "origin" not in run_git(["remote"], folder).split():
        return "it has no origin remote"
    origin = run_git(["remote", "get-url", "origin"], folder).strip()
    if not is_repo_url(origin, settings.organization, repo):
        shown = repr(without_credentials(origin))
        return f"its origin is {shown}, not {settings.organization}/{repo}"
    return None


def _update(folder: Path) -> tuple[str, str]:
    """Fetch ``folder`` and fast-forward it unless it has local changes or commits."""
    run_git(["fetch", "--quiet", "origin"], folder)
    before = _commit(folder, "HEAD")
    upstream = _upstream(folder)
    if upstream is None:
        if before is None:
            return "empty", ""
        return "not updated", "its checkout does not track a branch on origin"
    changed = bool(run_git(["status", "--porcelain", "--untracked-files=no"], folder))
    ahead = 0
    if before is not None:
        ahead = int(run_git(["rev-list", "--count", f"{upstream}..HEAD"], folder))
    if changed or ahead:
        reasons = ["local changes"] if changed else []
        if ahead:
            reasons.append(f"{ahead} local commit{'s' if ahead > 1 else ''}")
        return "not updated", " and ".join(reasons)
    run_git(["merge", "--ff-only", "--quiet", upstream], folder)
    return ("updated" if _commit(folder, "HEAD") != before else "up to date"), ""


def _upstream(folder: Path) -> str | None:
    """Return the branch on origin that the checkout tracks, if it has a commit."""
    if _commit(folder, "@{u}") is None:
        return None
    tracked = run_git(["rev-parse", "--symbolic-full-name", "@{u}"], folder).strip()
    return tracked if tracked.startswith("refs/remotes/origin/") else None


def _commit(folder: Path, ref: str) -> str | None:
    """Return the commit ``ref`` names in ``folder``, or None if there is none yet."""
    try:
        return run_git(["rev-parse", "--verify", "--quiet", ref], folder).strip()
    except GitError as error:
        if error.stderr:  # --quiet is silent only about a missing ref
            raise
        return None


def _late_commit(
    folder: Path, deadline: datetime | None, graders: set[str]
) -> datetime | None:
    """Return the time of the newest student commit on the origin branch if late.

    Commits by the grader (``graders``) and by GitHub Classroom do not count.
    """
    upstream = _upstream(folder) if deadline else None
    if upstream is None:
        return None
    log = run_git(
        ["log", f"--max-count={_LOG_LIMIT}", "--format=%cI%x00%ae%x00%an", upstream],
        folder,
    )
    for line in log.splitlines():
        when, email, author = line.split("\0")
        if author == CLASSROOM_BOT or {email.casefold(), author.casefold()} & graders:
            continue
        committed = datetime.fromisoformat(when)
        return committed if committed > deadline else None
    return None


def _grader_identity(root: Path) -> set[str]:
    """Return the casefolded git ``user.name`` and ``user.email`` of the grader."""
    identity = set()
    for key in ("user.name", "user.email"):
        with contextlib.suppress(GitError):
            identity.add(run_git(["config", key], root).strip().casefold())
    return identity - {""}


def _time(moment: datetime, deadline: datetime) -> str:
    """Format ``moment`` in the deadline's time zone, to the minute."""
    return moment.astimezone(deadline.tzinfo).isoformat(sep=" ", timespec="minutes")


def _positive_int(text: str) -> int:
    """Parse ``--jobs``, a whole number of at least 1."""
    if not text.isdigit() or int(text) < 1:
        raise argparse.ArgumentTypeError(
            f"{text!r} is not a whole number of at least 1"
        )
    return int(text)
