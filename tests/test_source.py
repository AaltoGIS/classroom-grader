import os
from pathlib import Path

import pytest

from classroom_grader import cli

SETTINGS = """\
organization = "IntroSDA-2026"
roster = "student_info.csv"

[assignments.Exercise-1]

[assignments.Final-assignment]
type = "group"
source_repo = "Sustainability-GIS-2023/Final-assignment"
"""
WHEN = "2026-11-01T12:00:00+02:00"


@pytest.fixture
def nbgrader_log(tmp_path, monkeypatch):
    """Put a fake ``nbgrader`` on PATH, as a relative entry, that logs its calls."""
    folder = tmp_path / "bin"
    folder.mkdir()
    (folder / "nbgrader").write_text(
        '#!/bin/sh\necho "$PWD $*" >> "$NBGRADER_LOG"\nexit "${NBGRADER_EXIT:-0}"\n'
    )
    (folder / "nbgrader").chmod(0o755)
    (folder / "nbgrader.cmd").write_text(
        '@echo off\r\necho %CD% %*>>"%NBGRADER_LOG%"\r\n'
        "if defined NBGRADER_EXIT exit /b %NBGRADER_EXIT%\r\n"
    )
    log = tmp_path / "nbgrader.log"
    monkeypatch.setenv("NBGRADER_LOG", str(log))
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PATH", f"bin{os.pathsep}{os.environ['PATH']}")
    return log


def logged_calls(log):
    """Return the logged nbgrader calls as (folder, arguments) pairs."""
    lines = log.read_text().splitlines() if log.exists() else []
    return [
        (Path(line.split(" ", 1)[0]).resolve(), line.split(" ", 1)[1]) for line in lines
    ]


def test_source_clones_updates_and_releases_with_nbgrader(
    course, github, nbgrader_log, capsys
):
    (course / "grader.toml").write_text(SETTINGS, encoding="utf-8")
    github.push("Exercise-1-grading", {"ex1.ipynb": "{}"}, "teacher", WHEN)
    github.push(
        "Final-assignment",
        {"final.ipynb": "{}"},
        "teacher",
        WHEN,
        owner="Sustainability-GIS-2023",
    )
    args = ["source", "Exercise-1", "final-assignment", "--course", str(course)]
    assert cli.main([*args, "--force"]) == 0
    assert capsys.readouterr().out == (
        "Exercise-1: IntroSDA-2026/Exercise-1-grading cloned into source/\n"
        "Final-assignment: Sustainability-GIS-2023/Final-assignment "
        "cloned into source/\n"
    )
    assert (course / "source" / "Final-assignment" / "final.ipynb").exists()

    github.push("Exercise-1-grading", {"ex1.ipynb": '{"cells": []}'}, "teacher", WHEN)
    assert cli.main(["source", "Exercise-1", "--course", str(course)]) == 0
    assert (
        capsys.readouterr().out
        == "Exercise-1: IntroSDA-2026/Exercise-1-grading updated\n"
    )
    assert (
        course / "source" / "Exercise-1" / "ex1.ipynb"
    ).read_text() == '{"cells": []}'
    root = course.resolve()
    assert logged_calls(nbgrader_log) == [
        (root, "db assignment add Exercise-1"),
        (root, "generate_assignment Exercise-1 --force"),
        (root, "db assignment add Final-assignment"),
        (root, "generate_assignment Final-assignment --force"),
        (root, "db assignment add Exercise-1"),
        (root, "generate_assignment Exercise-1"),
    ]


@pytest.mark.parametrize(
    ("case", "message"),
    [
        ("no nbgrader", "nbgrader is not on PATH"),
        ("no source repo", "IntroSDA-2026/Exercise-1-grading: git clone failed:"),
        ("wrong origin", "source/Exercise-1 is not used: its origin is "),
        (
            "nbgrader fails",
            "nbgrader db assignment add Exercise-1 failed with exit code 3",
        ),
    ],
)
def test_source_reports_what_it_cannot_do(
    course, github, nbgrader_log, monkeypatch, capsys, case, message
):
    (course / "grader.toml").write_text(SETTINGS, encoding="utf-8")
    if case != "no source repo":
        github.push("Exercise-1-grading", {"ex1.ipynb": "{}"}, "teacher", WHEN)
    if case == "no nbgrader":
        monkeypatch.setattr("classroom_grader.source.shutil.which", lambda name: None)
    if case == "wrong origin":
        github.push("Other", {"x": "1"}, "teacher", WHEN)
        bare = github.root / "IntroSDA-2026" / "Other.git"
        github.git("clone", "--quiet", str(bare), str(course / "source" / "Exercise-1"))
    if case == "nbgrader fails":
        monkeypatch.setenv("NBGRADER_EXIT", "3")
    assert cli.main(["source", "Exercise-1", "--course", str(course)]) == 1
    assert message in capsys.readouterr().err
