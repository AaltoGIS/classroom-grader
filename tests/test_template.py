import os

import pytest

from classroom_grader import cli
from classroom_grader.settings import load_settings
from classroom_grader.table import format_table
from classroom_grader.template import grading_template, template_text, unfilled_points

SETTINGS = """\
organization = "IntroSDA-2026"
roster = "student_info.csv"

[assignments.Exercise-1]
points = { "Problem 1" = 8, "Problem 2" = 11, "Problem 3" = 1 }

[assignments.Exercise-2]
"""
TEMPLATE = """\
## Grading
**Points:**
- Problem 1: /8 points
- Problem 2: /11 points
- Problem 3: /1 points

**Total: /20 points**

Comments:

Good job!
"""
WHEN = "2026-11-10T12:00:00+02:00"
BOT = "github-classroom[bot]"


def test_the_template_is_added_once_and_holds_back_the_push(course, github, capsys):
    (course / "grader.toml").write_text(SETTINGS, encoding="utf-8")
    (course / "student_info.csv").write_text(
        "user\nalice\nbob\ncarol\ndave\n", encoding="utf-8"
    )
    github.push("exercise-1-alice", {"README.md": "# Exercise 1\n"}, BOT, WHEN)
    bob_readme = {"README.md": "# Exercise 1\r\nWork"}
    github.push("exercise-1-bob", bob_readme, BOT, WHEN)
    github.push("exercise-1-carol", {"nb.ipynb": "{}\n"}, BOT, WHEN)
    course_option = ["--course", str(course)]
    assert cli.main(["fetch", "Exercise-1", *course_option]) == 0
    readme = {
        name: course / "submitted" / name / "Exercise-1" / "README.md"
        for name in ("alice", "bob", "carol")
    }
    capsys.readouterr()

    template = ["template", "Exercise-1", *course_option]
    assert cli.main(template) == 0
    assert capsys.readouterr().out == (
        "Exercise-1: 2 added, 1 created, 1 not fetched\n  dave: not fetched\n"
    )
    assert readme["alice"].read_text(encoding="utf-8") == f"# Exercise 1\n\n{TEMPLATE}"
    crlf = TEMPLATE.replace("\n", "\r\n")
    assert readme["bob"].read_bytes() == f"# Exercise 1\r\nWork\r\n\r\n{crlf}".encode()
    assert readme["carol"].read_text(encoding="utf-8") == TEMPLATE

    assert cli.main(template) == 0
    assert capsys.readouterr().out == (
        "Exercise-1: 3 already there, 1 not fetched\n  dave: not fetched\n"
    )
    assert cli.main(["template", "Exercise-2", *course_option]) == 1
    assert capsys.readouterr().err == (
        "grader: no points in grader.toml for Exercise-2; add them to the "
        'assignment\'s table, such as points = { "Problem 1" = 8 }\n'
    )

    filled = {"/8": "7/8", "/11": "10/11", "/1 ": "1/1 ", "/20": "18/20"}
    text = readme["alice"].read_text(encoding="utf-8")
    for blank, points in filled.items():
        text = text.replace(f": {blank}", f": {points}")
    readme["alice"].write_text(text, encoding="utf-8")
    text = readme["bob"].read_bytes().replace(b": /8", b": 8/8")
    readme["bob"].write_bytes(text)
    carol = readme["carol"].parent
    github.git("add", "README.md", cwd=carol)
    github.git("commit", "--quiet", "--message", "Template", cwd=carol)
    assert cli.main(["status", "Exercise-1", "--no-fetch", *course_option]) == 1
    states = [line.split()[1:4] for line in capsys.readouterr().out.splitlines()[2:5]]
    assert states == [
        ["feedback", "not", "committed"],
        ["template", "not", "filled"],
        ["template", "not", "filled"],
    ]

    assert cli.main(["push", "Exercise-1", *course_option]) == 0
    rows = [
        ["alice", "pushed", "commit feedback, push 1 commit"],
        ["bob", "template not filled", "no points for Problem 2, Problem 3, total"],
        [
            "carol",
            "template not filled",
            "no points for Problem 1, Problem 2, Problem 3, total",
        ],
        ["dave", "not fetched", "-"],
    ]
    table = format_table(["Student", "Result", "Details"], rows)
    summary = "1 pushed, 2 template not filled, 1 not fetched"
    assert capsys.readouterr().out == f"Exercise-1\n{table}\nExercise-1: {summary}\n"


def test_push_checks_the_template_in_the_commit_it_pushes(course, github, capsys):
    (course / "grader.toml").write_text(SETTINGS, encoding="utf-8")
    start = "# Exercise 1\n\nWork\non\nthe\nmaps\n"
    github.push("exercise-1-alice", {"README.md": start}, BOT, WHEN)
    course_option = ["--course", str(course)]
    assert cli.main(["fetch", "Exercise-1", *course_option]) == 0
    assert cli.main(["template", "Exercise-1", *course_option]) == 0
    readme = course / "submitted" / "alice" / "Exercise-1" / "README.md"
    readme.write_text(
        readme.read_text(encoding="utf-8").replace(": /", ": 1/"), encoding="utf-8"
    )
    student = {"README.md": f"- Problem 1: /8 points\n{start}"}
    github.push("exercise-1-alice", student, "alice", WHEN)
    remote = github.root / "IntroSDA-2026" / "exercise-1-alice.git"
    head = github.git("rev-parse", "main", cwd=remote)
    capsys.readouterr()

    assert cli.main(["push", "Exercise-1", *course_option]) == 0
    assert "alice    template not filled  no points for Problem 1" in (
        capsys.readouterr().out
    )
    assert github.git("rev-parse", "main", cwd=remote) == head


def test_a_layout_from_the_settings_and_its_unfilled_lines(course):
    (course / "grader.toml").write_text(
        """\
organization = "IntroSDA-2026"
roster = "student_info.csv"

[grading_template]
text = \"\"\"
# Feedback
{problems}
Total: {total}
{comment}\"\"\"
problem = "* {name}: ___ of {points}"
comment = "Well done"

[assignments.Exercise-5]
points = { "Task 1" = 5, "Task 2" = 9.1234567 }
comment = "Thank you for the valuable feedback! \U0001f642"
""",
        encoding="utf-8",
    )
    settings = load_settings(course)
    assignment = settings.assignments["Exercise-5"]
    text = grading_template(settings, assignment)
    assert text == (
        "# Feedback\n* Task 1: ___ of 5\n* Task 2: ___ of 9.1234567\n"
        "Total: 14.1234567\n"
        "Thank you for the valuable feedback! \U0001f642\n"
    )
    folder = course / "clone"
    folder.mkdir()
    readme = folder / "README.md"
    readme.write_text(text.replace("___ of 5", "4 of 5"), encoding="utf-8")
    text = template_text(settings, folder)
    assert unfilled_points(settings, assignment, text) == ["Task 2", "total"]


@pytest.mark.skipif(
    os.name == "nt", reason="symbolic links need extra rights on Windows"
)
def test_a_linked_readme_is_left_alone(course, github, capsys):
    (course / "grader.toml").write_text(SETTINGS, encoding="utf-8")
    github.push("exercise-1-alice", {"notes.md": "Mine\n"}, BOT, WHEN)
    assert cli.main(["fetch", "Exercise-1", "--course", str(course)]) == 0
    clone = course / "submitted" / "alice" / "Exercise-1"
    os.symlink("notes.md", clone / "README.md")
    capsys.readouterr()
    assert cli.main(["template", "Exercise-1", "--course", str(course)]) == 1
    assert capsys.readouterr().out == (
        "Exercise-1: 1 refused\n  alice: refused: README.md is a symbolic link\n"
    )
    assert (clone / "notes.md").read_text() == "Mine\n"
