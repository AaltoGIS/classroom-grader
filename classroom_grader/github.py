"""GitHub repository URLs in their HTTPS and SSH forms."""

import re

# Tests point this at a folder of bare repositories.
GITHUB_URL = "https://github.com"
_SSH_PREFIXES = ("git@github.com:", "ssh://git@github.com/")


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
