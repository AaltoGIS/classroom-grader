import pytest

from classroom_grader import cli

SETTINGS = """\
organization = "IntroSDA-2026"
roster = "student_info.csv"

[assignments.Exercise-1]
deadline = 2026-11-13T23:59:00+02:00

[assignments.Final-assignment]
type = "group"
"""
ON_TIME = "2026-11-10T12:00:00+02:00"


@pytest.fixture
def fetch_course(course, github):
    (course / "grader.toml").write_text(SETTINGS, encoding="utf-8")
    (course / "student_info.csv").write_text(
        "user\nalice\nbob\ncarol\ndave\nerin\nfrank\ngina\nhank\nivan\njo\n",
        encoding="utf-8",
    )
    return course


def test_fetch_clones_updates_and_lists_what_needs_attention(
    fetch_course, github, capsys
):
    for name in ("bob", "carol", "frank", "hank", "jo"):
        github.push(
            f"exercise-1-{name}",
            {"README.md": "Points:\n"},
            "github-classroom[bot]",
            ON_TIME,
        )
    github.create("exercise-1-ivan")
    assert cli.main(["fetch", "Exercise-1", "--course", str(fetch_course)]) == 0
    assert capsys.readouterr().out == (
        "Exercise-1: 5 cloned, 1 empty, 4 no repo\n"
        "Empty repository (nothing pushed yet):\n"
        "  ivan\n"
        "No repo (not accepted, or no access):\n"
        "  alice\n  dave\n  erin\n  gina\n"
    )
    submitted = fetch_course / "submitted"

    github.push(
        "exercise-1-alice", {"a.py": "1\n"}, "alice", "2026-11-14T08:00:00+02:00"
    )
    github.push("exercise-1-bob", {"b.py": "1\n"}, "bob", ON_TIME)
    github.push("exercise-1-ivan", {"i.py": "1\n"}, "ivan", ON_TIME)
    github.push("exercise-1-carol", {"c.py": "1\n"}, "carol", ON_TIME)
    (submitted / "carol" / "Exercise-1" / "README.md").write_text("Points: 9\n")
    github.push(
        "exercise-1-frank",
        {"README.md": "Points: 8\n"},
        "Grader",
        "2026-11-20T10:00:00+02:00",
    )
    hank = submitted / "hank" / "Exercise-1"
    (hank / "README.md").write_text("Points: 7\n")
    github.git("commit", "--quiet", "--all", "--message", "Add grading", cwd=hank)
    github.git(
        "clone",
        "--quiet",
        str(github.root / "IntroSDA-2026" / "exercise-1-bob.git"),
        str(submitted / "erin" / "Exercise-1"),
    )
    github.git("checkout", "--quiet", "--detach", cwd=submitted / "jo" / "Exercise-1")
    (submitted / "gina" / "Exercise-1").mkdir(parents=True)
    (submitted / "gina" / "Exercise-1" / "notes.txt").write_text("copied by hand\n")
    capsys.readouterr()

    assert (
        cli.main(["fetch", "exercise-1", "--course", str(fetch_course), "--jobs", "3"])
        == 1
    )
    bob_url = github.root / "IntroSDA-2026" / "exercise-1-bob.git"
    assert capsys.readouterr().out == (
        "Exercise-1: 1 cloned, 3 updated, 3 not updated, 2 refused, 1 no repo\n"
        "Not updated (fetched only):\n"
        "  carol: local changes\n"
        "  hank: 1 local commit\n"
        "  jo: its checkout does not track a branch on origin\n"
        "Refused:\n"
        f"  erin: its origin is {str(bob_url)!r}, not IntroSDA-2026/exercise-1-erin\n"
        "  gina: the folder exists but has no .git folder of its own\n"
        "No repo (not accepted, or no access):\n"
        "  dave\n"
        "Newest commit after the deadline 2026-11-13 23:59+02:00 "
        "(commit times come from the students' computers):\n"
        "  alice: 2026-11-14 08:00+02:00\n"
    )
    assert (submitted / "bob" / "Exercise-1" / "b.py").exists()
    assert (submitted / "ivan" / "Exercise-1" / "i.py").exists()
    carol = submitted / "carol" / "Exercise-1"
    assert not (carol / "c.py").exists()
    assert (
        github.git("log", "--format=%an", "-1", "origin/main", cwd=carol) == "carol\n"
    )
    assert not (submitted / "dave").exists()


def test_fetch_refuses_an_unknown_assignment(fetch_course, capsys):
    assert cli.main(["fetch", "Exercise-9", "--course", str(fetch_course)]) == 1
    assert (
        "not in grader.toml: Exercise-9; its assignments: Exercise-1, Final-assignment"
        in capsys.readouterr().err
    )
