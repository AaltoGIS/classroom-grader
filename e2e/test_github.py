"""End-to-end test against real GitHub, run by hand (see docs/development.md).

In the organization named by ``GRADER_E2E_ORG`` it creates private
repositories named as Classroom 50 names them, runs the grader commands on
them with real git and the real GitHub API, and deletes the repositories at
the end. ``grader source`` also needs nbgrader on PATH.
"""

import base64
import json
import os
import secrets
import shutil
import subprocess
import urllib.error
import urllib.request
from datetime import UTC, datetime, timedelta

import pytest

from classroom_grader import cli
from classroom_grader.git import TOKEN_VARIABLES, git_command
from classroom_grader.github import API_URL, repo_url

ORGANIZATION = os.environ.get("GRADER_E2E_ORG")
TOKEN = next((os.environ[n] for n in TOKEN_VARIABLES if os.environ.get(n)), None)
if not (ORGANIZATION and TOKEN):
    pytest.skip(
        "set GRADER_E2E_ORG and GH_TOKEN to run the end-to-end test",
        allow_module_level=True,
    )

# A new classroom name for each run, so that runs never share repositories.
CLASSROOM = f"e2e{secrets.token_hex(4)}"
EXERCISE = f"{CLASSROOM}-exercise-1"
GROUP = f"{CLASSROOM}-final-assignment"
SOURCE = f"{CLASSROOM}-source-exercise-1"
# The description of every repository the run creates; cleanup checks it.
MARKER = f"classroom-grader end-to-end test {CLASSROOM}"
NOW = datetime.now(UTC).replace(microsecond=0)
ON_TIME = (NOW - timedelta(days=2)).isoformat()
DEADLINE = (NOW - timedelta(days=1)).isoformat()
LATE = (NOW - timedelta(hours=1)).isoformat()
ROSTER = (
    "username,role,grader\n"
    "alice,student,Emma\nbob,student,Emma\ncarol,student,Emma\nemma-v,ta,\n"
)
NOTEBOOK = json.dumps(
    {
        "cells": [
            {
                "cell_type": "code",
                "execution_count": None,
                "id": "answer",
                "metadata": {
                    "nbgrader": {
                        "grade": False,
                        "grade_id": "answer",
                        "locked": False,
                        "schema_version": 3,
                        "solution": True,
                        "task": False,
                    }
                },
                "outputs": [],
                "source": [
                    "def answer():\n",
                    "    ### BEGIN SOLUTION\n",
                    "    return 42  # the model solution\n",
                    "    ### END SOLUTION\n",
                ],
            }
        ],
        "metadata": {
            "kernelspec": {
                "display_name": "Python 3",
                "language": "python",
                "name": "python3",
            }
        },
        "nbformat": 4,
        "nbformat_minor": 5,
    },
    indent=1,
)


def github_api(method, path, body=None):
    """Call the GitHub API with the test's token; return the JSON answer or None."""
    request = urllib.request.Request(
        f"{API_URL}{path}",
        data=None if body is None else json.dumps(body).encode(),
        method=method,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {TOKEN}",
            "Content-Type": "application/json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        data = response.read()
    return json.loads(data) if data else None


def git_with_token(*args, cwd, env=None):
    """Run git for test setup, passing the token the way the grader does."""
    result = subprocess.run(
        git_command(list(args)),
        cwd=cwd,
        env={**os.environ, "GIT_TERMINAL_PROMPT": "0", **(env or {})},
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, f"git {args[0]}: {result.stderr}"


class Repositories:
    """Repositories that the test creates in the organization and deletes again."""

    def __init__(self, work):
        self.work = work
        self.created = {}  # name -> id; None while the id is unknown

    def push(self, repo, files, author, when):
        """Commit ``files`` as ``author`` at ``when`` and push, creating the repo."""
        work = self.work / repo
        if not work.exists():
            self.created[repo] = None
            body = {"name": repo, "private": True, "description": MARKER}
            try:
                answer = github_api("POST", f"/orgs/{ORGANIZATION}/repos", body)
            except urllib.error.HTTPError as error:
                if error.code == 422:  # the name is taken: not this run's
                    del self.created[repo]
                raise
            self.created[repo] = answer["id"]
            work.mkdir()
            git_with_token("init", "--quiet", "--initial-branch=main", cwd=work)
            git_with_token(
                "remote", "add", "origin", repo_url(ORGANIZATION, repo), cwd=work
            )
        for name, text in files.items():
            (work / name).write_text(text, encoding="utf-8")
        email = f"{author}@example.org"
        identity = {
            "GIT_AUTHOR_NAME": author,
            "GIT_AUTHOR_EMAIL": email,
            "GIT_COMMITTER_NAME": author,
            "GIT_COMMITTER_EMAIL": email,
            "GIT_AUTHOR_DATE": when,
            "GIT_COMMITTER_DATE": when,
        }
        git_with_token("add", "--all", cwd=work)
        git_with_token(
            "commit", "--quiet", "-m", f"Work by {author}", cwd=work, env=identity
        )
        git_with_token("push", "--quiet", "origin", "HEAD:main", cwd=work)

    def commits(self, repo):
        """Return the messages of the commits on ``repo``'s main, newest first."""
        path = f"/repos/{ORGANIZATION}/{repo}/commits?sha=main&per_page=10"
        return [entry["commit"]["message"] for entry in github_api("GET", path)]

    def read(self, repo, name):
        """Return the text of the file ``name`` on ``repo``'s main."""
        entry = github_api(
            "GET", f"/repos/{ORGANIZATION}/{repo}/contents/{name}?ref=main"
        )
        return base64.b64decode(entry["content"]).decode()

    def delete_created(self):
        """Delete the repositories this test created; fail naming those left.

        A repository is deleted only if it has the id GitHub gave it at
        creation or, when that answer was lost, this run's description.
        """
        left = []
        for repo, repo_id in self.created.items():
            path = f"/repos/{ORGANIZATION}/{repo}"
            try:
                current = github_api("GET", path)
                if current["id"] == repo_id or (
                    repo_id is None and current.get("description") == MARKER
                ):
                    github_api("DELETE", path)
                else:
                    left.append(f"{repo} (not the repository this run created)")
            except Exception as error:  # go on with the other repositories
                if getattr(error, "code", None) != 404:
                    left.append(f"{repo} ({error!r})")
        assert not left, f"not deleted in {ORGANIZATION}: {'; '.join(left)}"


@pytest.fixture(scope="module")
def git_config(tmp_path_factory):
    """Git without the user's own configuration; the grader is ``Grader``."""
    config = tmp_path_factory.mktemp("git") / "gitconfig"
    config.write_text(
        "[user]\n\tname = Grader\n\temail = grader@example.org\n", encoding="utf-8"
    )
    with pytest.MonkeyPatch.context() as patch:
        patch.setenv("GIT_CONFIG_GLOBAL", str(config))
        patch.setenv("GIT_CONFIG_NOSYSTEM", "1")
        yield


@pytest.fixture(scope="module")
def organization(tmp_path_factory, git_config, pytestconfig):
    """Classroom 50 repositories: Alice (late), Bob, a team, and the teacher's."""
    plugins = pytestconfig.pluginmanager
    # Not captured: a terminal gets each line at once, during the setup.
    with plugins.get_plugin("capturemanager").global_and_fixture_disabled():
        plugins.get_plugin("terminalreporter").write_line(
            f"\nThis run's repositories start with {CLASSROOM}-"
        )
    org = Repositories(tmp_path_factory.mktemp("students"))
    try:
        start = {"README.md": "Points:\n", "work.txt": "First try\n"}
        org.push(f"{EXERCISE}-alice", start, "alice", ON_TIME)
        org.push(f"{EXERCISE}-alice", {"work.txt": "Second try\n"}, "alice", LATE)
        org.push(f"{EXERCISE}-bob", start, "bob", ON_TIME)
        org.push(GROUP, {"README.md": "Template\n"}, "teacher", ON_TIME)
        org.push(f"{GROUP}-group-1", start, "alice", ON_TIME)
        org.push(SOURCE, {"exercise.ipynb": NOTEBOOK}, "teacher", ON_TIME)
        yield org
    finally:
        org.delete_created()


@pytest.fixture(scope="module")
def course(tmp_path_factory, git_config):
    """A course folder written by ``grader init``, with a deadline and a group."""
    root = tmp_path_factory.mktemp("course")
    (root / "student_info.csv").write_text(ROSTER, encoding="utf-8")
    assert (
        grader(
            root,
            "init",
            "--organization",
            ORGANIZATION,
            "--classroom",
            CLASSROOM,
            "--roster",
            "student_info.csv",
            "--assignment",
            "Exercise-1",
            "--assignment",
            "Final-assignment",
        )
        == 0
    )
    settings = root / "grader.toml"
    text = settings.read_text(encoding="utf-8")
    text = text.replace(
        "[assignments.Exercise-1]\n",
        f"[assignments.Exercise-1]\ndeadline = {DEADLINE}\n"
        f'source_repo = "{ORGANIZATION}/{SOURCE}"\n',
    )
    text = text.replace(
        "[assignments.Final-assignment]\n",
        '[assignments.Final-assignment]\ntype = "group"\n',
    )
    settings.write_text(text, encoding="utf-8")
    return root


def grader(course, *args):
    """Run ``grader <args> --course <course>``; return the exit code."""
    return cli.main([*args, "--course", str(course)])


def table_row(out, name):
    """Return the line of ``out`` whose first word is ``name``, or ""."""
    lines = out.splitlines()
    return next((line for line in lines if line.split()[:1] == [name]), "")


def test_grading_round(organization, course, capsys):
    options = ["Exercise-1", "--grader", "Emma"]
    assert grader(course, "students", "--grader", "Emma") == 0
    out = capsys.readouterr().out
    assert out.endswith("\n3 students\n")
    assert "emma-v" not in out

    assert grader(course, "fetch", *options) == 0
    out = capsys.readouterr().out
    assert out.startswith("Exercise-1: 2 cloned, 1 no repo\n")
    assert table_row(out.partition("No repo")[2], "carol") == "  carol"
    assert table_row(out.partition("after the deadline")[2], "alice:")
    alice = course / "submitted" / "alice" / "Exercise-1"
    assert (alice / "work.txt").read_text(encoding="utf-8") == "Second try\n"

    organization.push(f"{EXERCISE}-bob", {"extra.txt": "More\n"}, "bob", LATE)
    assert grader(course, "status", *options) == 0
    out = capsys.readouterr().out
    assert "student pushed since" in table_row(out, "bob")
    assert "up to date" in table_row(out, "alice")
    assert "no repo" in table_row(out, "carol")

    for name in ("alice", "bob"):
        readme = course / "submitted" / name / "Exercise-1" / "README.md"
        readme.write_text(f"Points: 10\nGood work, {name}.\n", encoding="utf-8")
    assert grader(course, "status", *options) == 1
    out = capsys.readouterr().out
    assert "feedback not committed" in table_row(out, "alice")
    assert "feedback not committed" in table_row(out, "bob")

    before = organization.commits(f"{EXERCISE}-bob")
    assert grader(course, "push", *options, "--dry-run") == 0
    assert "would push" in table_row(capsys.readouterr().out, "bob")
    assert organization.commits(f"{EXERCISE}-bob") == before

    assert grader(course, "push", *options) == 0
    out = capsys.readouterr().out
    assert "pushed" in table_row(out, "alice")
    assert "pushed" in table_row(out, "bob")
    assert organization.commits(f"{EXERCISE}-bob")[:3] == [
        "Add grading",
        "Work by bob",
        "Work by bob",
    ]
    assert "Good work, bob." in organization.read(f"{EXERCISE}-bob", "README.md")
    assert "Good work, alice." in organization.read(f"{EXERCISE}-alice", "README.md")

    assert grader(course, "status", *options) == 0
    out = capsys.readouterr().out
    assert "up to date" in table_row(out, "alice")
    assert "up to date" in table_row(out, "bob")


def test_group_assignment_finds_the_teams(organization, course, capsys):
    assert grader(course, "fetch", "Final-assignment") == 0
    assert capsys.readouterr().out.startswith("Final-assignment: 1 cloned\n")
    teams = [
        folder.name
        for folder in (course / "submitted").iterdir()
        if (folder / "Final-assignment").is_dir()
    ]
    assert teams == ["group-1"]
    readme = course / "submitted" / "group-1" / "Final-assignment" / "README.md"
    readme.write_text("Points: 20\n", encoding="utf-8")
    assert grader(course, "push", "Final-assignment", "--student", "group-1") == 0
    assert organization.commits(f"{GROUP}-group-1")[0] == "Add grading"


@pytest.mark.skipif(shutil.which("nbgrader") is None, reason="needs nbgrader")
def test_source_releases_the_teachers_notebook(organization, course):
    assert grader(course, "source", "Exercise-1") == 0
    assert (course / "source" / "Exercise-1" / "exercise.ipynb").is_file()
    release = course / "release" / "Exercise-1" / "exercise.ipynb"
    released = release.read_text(encoding="utf-8")
    assert "model solution" not in released
    assert "YOUR CODE HERE" in released
