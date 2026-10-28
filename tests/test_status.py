import json

import pytest

from classroom_grader import cli, repo
from classroom_grader.table import format_table

SETTINGS = """\
organization = "IntroSDA-2026"
roster = "student_info.csv"
feedback_files = ["README.md", "grades/notes.md"]

[assignments.Exercise-1]
deadline = 2026-11-13T23:59:00+02:00
"""
ON_TIME = "2026-11-10T12:00:00+02:00"
BOT = "github-classroom[bot]"


def notebook(version, cell_metadata):
    cell = {"cell_type": "code", "execution_count": None, "metadata": cell_metadata}
    cell |= {"outputs": [], "source": ["x = 1"]}
    return json.dumps(
        {
            "cells": [cell],
            "metadata": {"language_info": {"version": version}},
            "nbformat": 4,
            "nbformat_minor": 5,
        }
    )


@pytest.fixture
def graded_course(course, github):
    """A fetched course whose clones are in every state ``grader status`` knows."""
    (course / "grader.toml").write_text(SETTINGS, encoding="utf-8")
    (course / "student_info.csv").write_text(
        "user\nalice\nbob\ncarol\ndave\nerin\nfrank\ngina\nhank\nivan\njo\n",
        encoding="utf-8",
    )
    for name in ("alice", "bob", "carol", "erin", "jo"):
        github.push(f"exercise-1-{name}", {"README.md": "Points:\n"}, BOT, ON_TIME)
    dave_files = {"README.md": "Points:\n", ".gitignore": "grades/\n"}
    github.push("exercise-1-dave", dave_files, BOT, ON_TIME)
    files = {"README.md": "", "x.py": "1\n", "nb.ipynb": notebook("3.11.6", {})}
    files |= {"staged.ipynb": notebook("3.11.6", {}), "bad.ipynb": '{"cells": null}'}
    files |= {"old.py": "1\n", "deep.ipynb": "{}", "bool.ipynb": '{"x": 1}'}
    github.push("exercise-1-hank", files, "hank", "2026-11-14T08:00:00+02:00")
    github.create("exercise-1-ivan")
    assert cli.main(["fetch", "Exercise-1", "--course", str(course)]) == 0

    clones = course / "submitted"
    github.push("exercise-1-alice", {"a.py": "1\n"}, "alice", ON_TIME)
    (clones / "bob" / "Exercise-1" / "README.md").write_text("Points: 9\n")
    for name in ("carol", "erin"):
        (clones / name / "Exercise-1" / "README.md").write_text("Points: 8\n")
        github.git(
            "commit",
            "--quiet",
            "--all",
            "-m",
            "Add grading",
            cwd=clones / name / "Exercise-1",
        )
    github.push("exercise-1-erin", {"e.py": "1\n"}, "erin", ON_TIME)
    github.push("exercise-1-gina", {"g.py": "1\n"}, "gina", ON_TIME)
    github.git("checkout", "--quiet", "--detach", cwd=clones / "jo" / "Exercise-1")
    hank = clones / "hank" / "Exercise-1"
    (hank / "nb.ipynb").write_text(notebook("3.12.5", {"collapsed": True}))
    (hank / "staged.ipynb").write_text(notebook("3.12.5", {}))
    github.git("add", "staged.ipynb", cwd=hank)
    (hank / "bad.ipynb").write_text('{"cells": null, "metadata": {}}')
    (hank / "deep.ipynb").write_text("[" * 100_000 + "]" * 100_000)
    (hank / "bool.ipynb").write_text('{"x": true}')
    (hank / ".ipynb_checkpoints").mkdir()
    (hank / ".ipynb_checkpoints" / "nb-checkpoint.ipynb").write_text("{}")
    github.git("mv", "old.py", ".ipynb_checkpoints/old.py", cwd=hank)
    (clones / "dave" / "Exercise-1" / "grades").mkdir()
    (clones / "dave" / "Exercise-1" / "grades" / "notes.md").write_text("Points: 7\n")

    (hank / "x.py").write_text("2\n")
    return course


@pytest.mark.parametrize(
    ("options", "fetched_states", "summary"),
    [
        (
            [],
            ["student pushed since", "diverged", "no repo"],
            "1 up to date, 1 student pushed since, 2 feedback not committed, "
            "1 not pushed, 1 diverged, 1 empty, 1 not fetched, 1 no repo, 1 refused",
        ),
        (
            ["--no-fetch"],
            ["up to date", "not pushed", "not fetched"],
            "2 up to date, 2 feedback not committed, 2 not pushed, 1 empty, "
            "2 not fetched, 1 refused",
        ),
    ],
    ids=["fetch-first", "no-fetch"],
)
def test_status_shows_where_each_students_feedback_is(
    graded_course, capsys, options, fetched_states, summary
):
    capsys.readouterr()
    assert (
        cli.main(["status", "Exercise-1", "--course", str(graded_course), *options])
        == 1
    )
    alice, erin, frank = fetched_states
    rows = [
        ["alice", alice, "-", "-"],
        ["bob", "feedback not committed", "-", "-"],
        ["carol", "not pushed", "-", "-"],
        ["dave", "feedback not committed", "-", "-"],
        ["erin", erin, "-", "-"],
        ["frank", frank, "-", "-"],
        ["gina", "not fetched", "-", "-"],
        [
            "hank",
            "up to date",
            "old.py, bad.ipynb (metadata only), bool.ipynb, deep.ipynb, "
            "nb.ipynb (metadata only), staged.ipynb (metadata only), x.py",
            "2026-11-14 08:00+02:00",
        ],
        ["ivan", "empty", "-", "-"],
        ["jo", "refused", "-", "-"],
    ]
    table = format_table(["Student", "State", "Other local changes", "Late"], rows)
    refused = "Refused or failed:\n  jo: its checkout does not track a branch on origin"
    assert capsys.readouterr().out == (
        f"Exercise-1\n{table}\n{refused}\nExercise-1: {summary}\n"
    )


def test_status_exit_code_is_0_when_no_feedback_is_waiting(graded_course):
    students = ["alice", "frank", "gina", "hank", "ivan"]
    options = [option for name in students for option in ("--student", name)]
    assert (
        cli.main(["status", "Exercise-1", "--course", str(graded_course), *options])
        == 0
    )


def test_notebooks_over_the_size_limit_are_not_parsed(
    graded_course, monkeypatch, capsys
):
    monkeypatch.setattr(repo, "NOTEBOOK_LIMIT", 10)
    capsys.readouterr()
    options = ["--student", "hank", "--no-fetch"]
    cli.main(["status", "Exercise-1", "--course", str(graded_course), *options])
    changes = "old.py, bad.ipynb, bool.ipynb, deep.ipynb, nb.ipynb, staged.ipynb, x.py"
    assert f"hank     up to date  {changes}" in capsys.readouterr().out
