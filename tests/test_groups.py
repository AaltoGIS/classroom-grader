import pytest

from classroom_grader import cli

SETTINGS = """\
organization = "Sustainability-GIS-2026"
roster = "student_info.csv"

[assignments.Final-assignment]
type = "group"
repo_prefix = "final-assignment"
source_repo = "Sustainability-GIS-2023/Final-assignment"
"""
ORG = "Sustainability-GIS-2026"
WHEN = "2026-12-01T12:00:00+02:00"


@pytest.fixture
def group_course(course, github, monkeypatch):
    """A course with one group assignment and two team repositories on GitHub."""
    (course / "grader.toml").write_text(SETTINGS, encoding="utf-8")
    for team in ("group-1", "Bikers"):
        github.push(
            f"final-assignment-{team}",
            {"README.md": "Points:\n"},
            team,
            WHEN,
            owner=ORG,
        )

    def teams(organization, prefix):
        assert (organization, prefix) == (ORG, "final-assignment")
        return ["group-1", "Bikers"]

    monkeypatch.setattr("classroom_grader.course.team_names", teams)
    return course


def test_teams_are_fetched_checked_and_pushed_like_students(
    group_course, github, capsys
):
    args = ["Final-assignment", "--course", str(group_course)]
    assert cli.main(["fetch", *args, "--grader", "Nobody"]) == 0
    assert capsys.readouterr().out == "Final-assignment: 2 cloned\n"
    bikers = group_course / "submitted" / "Bikers" / "Final-assignment"
    (bikers / "README.md").write_text("Points: 18\n")
    assert cli.main(["status", *args, "--no-fetch"]) == 1
    assert "Team     State" in capsys.readouterr().out
    assert cli.main(["push", *args, "--student", "bikers"]) == 0
    out = capsys.readouterr().out
    assert "Bikers  pushed  commit feedback, push 1 commit" in out
    assert "group-1" not in out
    bare = github.root / ORG / "final-assignment-Bikers.git"
    assert github.git("log", "-1", "--format=%s", "main", cwd=bare) == "Add grading\n"


@pytest.mark.parametrize(
    ("roster", "options", "message"),
    [
        ("user\nGroup-1\n", [], "the teams group-1 have the names of roster students"),
        (
            "user\nalice\n",
            ["--student", "zed"],
            "no selected student or team is called zed",
        ),
    ],
)
def test_teams_that_clash_or_are_unknown_are_refused(
    group_course, capsys, roster, options, message
):
    (group_course / "student_info.csv").write_text(roster, encoding="utf-8")
    args = ["fetch", "Final-assignment", "--course", str(group_course), *options]
    assert cli.main(args) == 1
    assert message in capsys.readouterr().err
