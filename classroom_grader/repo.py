"""Checks and git queries on the student clones in ``submitted/``."""

import contextlib
from datetime import datetime
from pathlib import Path

from classroom_grader.git import GitError, run_git
from classroom_grader.github import is_repo_url, without_credentials
from classroom_grader.settings import Assignment, Settings

CLASSROOM_BOT = "github-classroom[bot]"
# Parts of git's messages for a repository that is missing or not visible: from
# GitHub over HTTPS or SSH, and for a local path.
_MISSING_REPO = (
    "repository not found",
    "does not exist",
    "does not appear to be a git repository",
)
# Commits searched, newest first, for the newest student commit.
_LOG_LIMIT = 1000


def repo_name(assignment: Assignment, name: str) -> str:
    """Return the Classroom repository name of student or team ``name``."""
    return f"{assignment.repo_prefix}-{name}"


def is_missing_repo(error: GitError) -> bool:
    """Tell whether git failed because the repository is missing or not visible."""
    return any(text in error.stderr.lower() for text in _MISSING_REPO)


def is_unfetched(folder: Path) -> bool:
    """Tell whether ``folder`` is missing or an empty folder, ready for a clone."""
    return not folder.exists() or (folder.is_dir() and not any(folder.iterdir()))


def leads_outside(settings: Settings, folder: Path) -> str | None:
    """Say so when ``folder`` resolves outside ``submitted/``, through a link."""
    submitted = (settings.root / "submitted").resolve()
    if folder.resolve().is_relative_to(submitted):
        return None
    return f"the folder leads outside {submitted}"


def clone_problem(settings: Settings, folder: Path, repo: str) -> str | None:
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


def commit(folder: Path, ref: str) -> str | None:
    """Return the commit ``ref`` names in ``folder``, or None if there is none yet."""
    try:
        return run_git(["rev-parse", "--verify", "--quiet", ref], folder).strip()
    except GitError as error:
        if error.stderr:  # --quiet is silent only about a missing ref
            raise
        return None


def upstream(folder: Path) -> str | None:
    """Return the branch on origin that the checkout tracks, if it has a commit."""
    if commit(folder, "@{u}") is None:
        return None
    tracked = run_git(["rev-parse", "--symbolic-full-name", "@{u}"], folder).strip()
    return tracked if tracked.startswith("refs/remotes/origin/") else None


def late_commit(
    folder: Path, deadline: datetime | None, graders: set[str]
) -> datetime | None:
    """Return the time of the newest student commit on the origin branch if late.

    Commits by the grader (``graders``) and by GitHub Classroom do not count.
    """
    tracked = upstream(folder) if deadline else None
    if tracked is None:
        return None
    log = run_git(
        ["log", f"--max-count={_LOG_LIMIT}", "--format=%cI%x00%ae%x00%an", tracked],
        folder,
    )
    for line in log.splitlines():
        when, email, author = line.split("\0")
        if author == CLASSROOM_BOT or {email.casefold(), author.casefold()} & graders:
            continue
        committed = datetime.fromisoformat(when)
        return committed if committed > deadline else None
    return None


def grader_identity(root: Path) -> set[str]:
    """Return the casefolded git ``user.name`` and ``user.email`` of the grader."""
    identity = set()
    for key in ("user.name", "user.email"):
        with contextlib.suppress(GitError):
            identity.add(run_git(["config", key], root).strip().casefold())
    return identity - {""}


def format_time(moment: datetime, deadline: datetime) -> str:
    """Format ``moment`` in the deadline's time zone, to the minute."""
    return moment.astimezone(deadline.tzinfo).isoformat(sep=" ", timespec="minutes")
