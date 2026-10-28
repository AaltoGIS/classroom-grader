"""Run git without prompts, with an optional token from the environment."""

import os
import subprocess
from pathlib import Path

from classroom_grader import GraderError

TOKEN_VARIABLES = ("GH_TOKEN", "GITHUB_TOKEN")
# Reads the token when git asks for it, so it never appears in arguments,
# remote URLs or .git/config.
_TOKEN_HELPER = (
    "!f() { echo username=x-access-token; "
    'echo "password=${GH_TOKEN:-$GITHUB_TOKEN}"; }; f'
)


class GitError(GraderError):
    """A git command failed; ``stderr`` holds git's message."""

    def __init__(self, args: list[str], stderr: str):
        self.stderr = stderr.strip()
        last_line = self.stderr.splitlines()[-1] if self.stderr else "no message"
        super().__init__(f"git {args[0]} failed: {last_line}")


def git_command(args: list[str]) -> list[str]:
    """Return the command line for ``git <args>``, with the token helper if needed."""
    if not any(os.environ.get(name) for name in TOKEN_VARIABLES):
        return ["git", *args]
    return [
        "git",
        "-c",
        "credential.helper=",
        "-c",
        f"credential.helper={_TOKEN_HELPER}",
        *args,
    ]


def run_git(args: list[str], cwd: Path | None = None) -> str:
    """Run ``git <args>`` in ``cwd``; return its output or raise ``GitError``.

    Git gets no input and may not ask for credentials on the terminal (SSH keys
    need an agent), and it writes its messages in English so that callers can
    recognise them.
    """
    result = subprocess.run(
        git_command(args),
        cwd=cwd,
        env={**os.environ, "GIT_TERMINAL_PROMPT": "0", "LC_ALL": "C"},
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode != 0:
        raise GitError(args, result.stderr)
    return result.stdout
