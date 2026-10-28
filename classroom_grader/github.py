"""GitHub: repository URLs in their HTTPS and SSH forms, and the REST API."""

import http.client
import json
import os
import re
import subprocess
import urllib.error
import urllib.request
from typing import Any

from classroom_grader import GraderError
from classroom_grader.git import TOKEN_VARIABLES
from classroom_grader.settings import folder_name_problem

# Tests point these at a folder of bare repositories and at a local server.
GITHUB_URL = "https://github.com"
API_URL = "https://api.github.com"
# Prints the token of a logged-in GitHub CLI.
GH_TOKEN_COMMAND = ["gh", "auth", "token"]
_SSH_PREFIXES = ("git@github.com:", "ssh://git@github.com/")
_NEXT_LINK = re.compile(r'<([^>]+)>;\s*rel="next"')
_TEAM = re.compile(r"[A-Za-z0-9._-]+")


def repo_url(owner: str, repo: str, protocol: str = "https") -> str:
    """Return the clone URL of ``owner/repo`` for ``protocol`` ("https" or "ssh")."""
    if protocol == "ssh":
        return f"git@github.com:{owner}/{repo}.git"
    return f"{GITHUB_URL}/{owner}/{repo}.git"


def parse_repo_url(url: str) -> tuple[str, str] | None:
    """Return ``(owner, repo)`` of a GitHub HTTPS or SSH URL; None for other URLs."""
    for prefix in (f"{GITHUB_URL}/", "https://github.com/", *_SSH_PREFIXES):
        if url[: len(prefix)].lower() == prefix.lower():
            path = url[len(prefix) :].rstrip("/").removesuffix(".git")
            owner, slash, repo = path.partition("/")
            if owner and slash and repo and "/" not in repo:
                return owner, repo
    return None


def is_repo_url(url: str, owner: str, repo: str) -> bool:
    """Tell whether ``url`` points at ``owner/repo``, ignoring case and URL form."""
    parsed = parse_repo_url(url)
    return parsed is not None and (
        parsed[0].casefold(),
        parsed[1].casefold(),
    ) == (owner.casefold(), repo.casefold())


def without_credentials(url: str) -> str:
    """Return ``url`` without a ``user:password@`` part, which may hold a token."""
    return re.sub(r"^([a-z][a-z0-9+.-]*://)[^/@]*@", r"\1", url, flags=re.IGNORECASE)


def github_token() -> str | None:
    """Return the token in GH_TOKEN or GITHUB_TOKEN, else the GitHub CLI's token."""
    for name in TOKEN_VARIABLES:
        if token := os.environ.get(name):
            return token
    try:
        result = subprocess.run(
            GH_TOKEN_COMMAND,
            capture_output=True,
            text=True,
            stdin=subprocess.DEVNULL,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return (result.stdout.strip() or None) if result.returncode == 0 else None


def get_json(url: str, token: str | None) -> tuple[Any, str | None]:
    """GET one page of the GitHub API; return its JSON and the next page's URL.

    The token is not passed on if GitHub redirects the request elsewhere.
    """
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "classroom-grader",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    if token:
        request.add_unredirected_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            data = json.load(response)
            link = response.headers.get("Link", "")
    except urllib.error.HTTPError as error:
        raise GraderError(
            f"GitHub answered {error.code} {error.reason} for {url}"
        ) from None
    except (
        urllib.error.URLError,
        http.client.HTTPException,
        OSError,
        ValueError,
    ) as error:
        raise GraderError(f"could not read {url}: {error}") from None
    match = _NEXT_LINK.search(link)
    next_url = match.group(1) if match else None
    return data, next_url if next_url and next_url.startswith(f"{API_URL}/") else None


def team_names(organization: str, prefix: str) -> list[str]:
    """Return the teams of ``organization``'s repositories named ``<prefix>-<team>``.

    The prefix matches in any case. The repository named just ``prefix`` (the
    assignment's template) is not a team; a team name that is not a safe
    folder name on Windows, macOS and Linux is left out, and a team listed
    twice (the pages can shift while they are read) is kept once.
    """
    token = github_token()
    url: str | None = f"{API_URL}/orgs/{organization}/repos?per_page=100"
    teams: dict[str, str] = {}
    while url:
        page, url = get_json(url, token)
        for repo in page if isinstance(page, list) else []:
            name = repo.get("name", "") if isinstance(repo, dict) else ""
            if name[: len(prefix) + 1].lower() == f"{prefix.lower()}-":
                team = name[len(prefix) + 1 :]
                if _is_team_folder(team):
                    teams.setdefault(team.casefold(), team)
    return list(teams.values())


def _is_team_folder(team: str) -> bool:
    """Tell whether ``team`` can be used as the folder ``submitted/<team>``."""
    return (
        bool(_TEAM.fullmatch(team))
        and team.casefold() != ".git"
        and folder_name_problem(team) is None
    )
