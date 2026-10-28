import os
import subprocess

import pytest

from classroom_grader.git import git_command
from classroom_grader.github import is_repo_url, parse_repo_url, without_credentials


@pytest.mark.parametrize(
    ("url", "parsed"),
    [
        (
            "https://github.com/IntroSDA-2026/exercise-1-Aida.git",
            ("IntroSDA-2026", "exercise-1-Aida"),
        ),
        ("https://GitHub.com/o/r/", ("o", "r")),
        ("git@github.com:o/r.git", ("o", "r")),
        ("ssh://git@github.com/o/r", ("o", "r")),
        ("https://gitlab.com/o/r.git", None),
        ("https://github.com/o/r/tree/main", None),
        ("https://github.com/o", None),
    ],
)
def test_github_urls_are_parsed_in_https_and_ssh_form(url, parsed):
    assert parse_repo_url(url) == parsed


def test_repo_url_comparison_ignores_case_and_form():
    assert is_repo_url(
        "git@github.com:INTROSDA-2026/Exercise-1-aida",
        "IntroSDA-2026",
        "exercise-1-Aida",
    )
    assert not is_repo_url(
        "https://github.com/IntroSDA-2026/exercise-1-bob",
        "IntroSDA-2026",
        "exercise-1-Aida",
    )


@pytest.mark.parametrize(
    ("url", "shown"),
    [
        (
            "https://x-access-token:abc123@github.com/o/r.git",
            "https://github.com/o/r.git",
        ),
        ("git@github.com:o/r.git", "git@github.com:o/r.git"),
    ],
)
def test_credentials_are_left_out_of_shown_urls(url, shown):
    assert without_credentials(url) == shown


@pytest.mark.parametrize("variable", ["GH_TOKEN", "GITHUB_TOKEN"])
def test_token_reaches_git_only_through_the_credential_helper(
    github, monkeypatch, variable
):
    monkeypatch.setenv(variable, "secret-token")
    command = git_command(["credential", "fill"])
    assert "secret-token" not in " ".join(command)
    answer = subprocess.run(
        command,
        input="protocol=https\nhost=github.com\n\n",
        env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
        capture_output=True,
        text=True,
        check=True,
    )
    assert "password=secret-token" in answer.stdout.splitlines()
