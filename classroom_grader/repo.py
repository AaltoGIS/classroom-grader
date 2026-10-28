"""Checks and git queries on the student clones in ``submitted/``."""

import contextlib
import json
from datetime import datetime
from pathlib import Path, PurePosixPath
from typing import Any

from classroom_grader.git import GitError, run_git
from classroom_grader.github import is_repo_url, without_credentials
from classroom_grader.settings import Assignment
from classroom_grader.table import printable

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
NOISE_FOLDER = ".ipynb_checkpoints"
# Larger notebooks (in bytes) are not parsed to look for metadata-only changes.
NOTEBOOK_LIMIT = 20_000_000


def repo_name(assignment: Assignment, name: str) -> str:
    """Return the Classroom repository name of student or team ``name``."""
    return f"{assignment.repo_prefix}-{name}"


def is_missing_repo(error: GitError) -> bool:
    """Tell whether git failed because the repository is missing or not visible."""
    return any(text in error.stderr.lower() for text in _MISSING_REPO)


def is_unfetched(folder: Path) -> bool:
    """Tell whether ``folder`` is missing or an empty folder, ready for a clone."""
    return not folder.exists() or (folder.is_dir() and not any(folder.iterdir()))


def leads_outside(folder: Path, base: Path) -> str | None:
    """Say so when ``folder`` resolves outside ``base``, through a link."""
    base = base.resolve()
    if folder.resolve().is_relative_to(base):
        return None
    return f"the folder leads outside {base}"


def clone_problem(folder: Path, owner: str, repo: str) -> str | None:
    """Say why ``folder`` is not a clone of the expected repository, if it is not."""
    git_folder = folder / ".git"
    if git_folder.is_symlink() or not git_folder.is_dir():
        return "the folder exists but has no .git folder of its own"
    if "origin" not in run_git(["remote"], folder).split():
        return "it has no origin remote"
    origin = run_git(["remote", "get-url", "origin"], folder).strip()
    if not is_repo_url(origin, owner, repo):
        shown = repr(without_credentials(origin))
        return f"its origin is {shown}, not {owner}/{repo}"
    push_urls = run_git(["remote", "get-url", "--push", "--all", "origin"], folder)
    for url in push_urls.splitlines():
        if not is_repo_url(url, owner, repo):
            shown = repr(without_credentials(url))
            return f"its push URL is {shown}, not {owner}/{repo}"
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


def literal_pathspecs(paths: list[str] | tuple[str, ...]) -> list[str]:
    """Return ``paths`` as pathspecs that git does not read as patterns."""
    return [f":(literal){path}" for path in paths]


def ahead_behind(folder: Path, tracked: str) -> tuple[int, int]:
    """Return how many commits HEAD has that ``tracked`` lacks, and the reverse."""
    counts = run_git(
        ["rev-list", "--left-right", "--count", f"HEAD...{tracked}"], folder
    )
    ahead, behind = (int(count) for count in counts.split())
    return ahead, behind


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


def local_changes(
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
        + literal_pathspecs(sorted(feedback)),
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


def clone_into(url: str, folder: Path) -> None:
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


def fast_forward(folder: Path) -> tuple[str, str]:
    """Fetch ``folder`` and fast-forward it unless it has local changes or commits.

    Return the state ("updated", "up to date", "empty" or "not updated") and,
    for "not updated", the reason.
    """
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
