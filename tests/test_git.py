import http.server
import json
import os
import subprocess
import sys
import threading

import pytest

from classroom_grader import GraderError
from classroom_grader.git import TOKEN_VARIABLES, git_command
from classroom_grader.github import (
    github_token,
    is_repo_url,
    parse_repo_url,
    team_names,
    without_credentials,
)


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


@pytest.fixture
def api(monkeypatch):
    """A local server standing in for the GitHub API.

    Fill ``pages`` with path -> (status, JSON body, path of the next page);
    ``requests`` collects (path, Authorization header) per request.
    """
    pages, requests = {}, []

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            requests.append((self.path, self.headers.get("Authorization")))
            status, body, next_path = pages.get(self.path, (404, {}, None))
            self.send_response(status)
            if next_path:
                self.send_header("Link", f'<{base}{next_path}>; rel="next"')
            self.end_headers()
            self.wfile.write(json.dumps(body).encode())

        def log_message(self, *args):
            pass

    server = http.server.HTTPServer(("127.0.0.1", 0), Handler)
    base = f"http://127.0.0.1:{server.server_port}"
    threading.Thread(target=server.serve_forever, daemon=True).start()
    monkeypatch.setattr("classroom_grader.github.API_URL", base)
    yield pages, requests
    server.shutdown()
    server.server_close()


def test_team_names_follow_pages_and_send_the_token(api, monkeypatch):
    pages, requests = api
    monkeypatch.setenv("GH_TOKEN", "secret-token")
    first, second = (
        "/orgs/Org/repos?per_page=100",
        "/orgs/Org/repos?per_page=100&page=2",
    )
    template = {"name": "final-assignment"}
    pages[first] = (200, [template, {"name": "final-assignment-group-1"}], second)
    pages[second] = (
        200,
        [
            {"name": "Final-Assignment-Bikers"},
            {"name": "final-assignment-.."},
            {"name": "exercise-1-alice"},
            {"name": "final-assignment-CON"},
            {"name": "final-assignment-.git"},
            {"name": "final-assignment-GROUP-1"},
        ],
        None,
    )
    assert team_names("Org", "final-assignment") == ["group-1", "Bikers"]
    assert requests == [(first, "Bearer secret-token"), (second, "Bearer secret-token")]


def test_api_errors_are_reported(api, monkeypatch):
    for name in TOKEN_VARIABLES:
        monkeypatch.delenv(name, raising=False)
    no_cli = [sys.executable, "-c", "raise SystemExit(1)"]
    monkeypatch.setattr("classroom_grader.github.GH_TOKEN_COMMAND", no_cli)
    with pytest.raises(GraderError, match="GitHub answered 404"):
        team_names("Nobody", "final-assignment")


@pytest.mark.parametrize(
    ("command", "token"),
    [
        ([sys.executable, "-c", "print('cli-token')"], "cli-token"),
        ([sys.executable, "-c", "raise SystemExit(1)"], None),
        (["no-such-github-cli"], None),
    ],
)
def test_token_falls_back_to_the_github_cli(monkeypatch, command, token):
    for name in TOKEN_VARIABLES:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr("classroom_grader.github.GH_TOKEN_COMMAND", command)
    assert github_token() == token
