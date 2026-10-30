import pytest
from traitlets.config.loader import PyFileConfigLoader

from classroom_grader import cli
from classroom_grader.init import GITIGNORE_LINES
from classroom_grader.settings import load_settings

FLAGS = [
    "--organization",
    "IntroSDA-2026",
    "--classroom",
    "introsda",
    "--roster",
    "student_info.csv",
]


def answer(monkeypatch, *answers):
    """Make ``input()`` return ``answers`` in turn, then behave as end of input."""
    replies = iter(answers)

    def fake_input(prompt):
        try:
            return next(replies)
        except StopIteration:
            raise EOFError from None

    monkeypatch.setattr("builtins.input", fake_input)


@pytest.mark.parametrize(
    ("flags", "answers", "prefix"),
    [
        (
            [*FLAGS, "--assignment", "Exercise-1", "--assignment", "Exercise.2"],
            [],
            "introsda-exercise-1",
        ),
        ([], ["IntroSDA-2026", "", "", "Exercise-1, Exercise.2"], "exercise-1"),
    ],
    ids=["options", "questions-without-classroom"],
)
def test_init_writes_settings_and_nbgrader_config(
    course, monkeypatch, flags, answers, prefix
):
    answer(monkeypatch, *answers)
    assert cli.main(["init", "--course", str(course), *flags]) == 0
    settings = load_settings(course)
    assert settings.organization == "IntroSDA-2026"
    assert settings.roster == course / "student_info.csv"
    assert list(settings.assignments) == ["Exercise-1", "Exercise.2"]
    assert settings.assignments["Exercise-1"].repo_prefix == prefix
    config = PyFileConfigLoader("nbgrader_config.py", path=str(course)).load_config()
    assert config.CourseDirectory.root == str(course)
    assert config.CourseDirectory.course_id == "IntroSDA-2026"
    gitignore = (course / ".gitignore").read_text(encoding="utf-8")
    assert gitignore.splitlines() == list(GITIGNORE_LINES)


@pytest.mark.parametrize(
    ("old", "added"),
    [
        ("*.pyc", "\n" + "\n".join(GITIGNORE_LINES) + "\n"),
        ("submitted/\r\n.DS_Store\r\n", "\n".join(GITIGNORE_LINES[1:]) + "\n"),
        ("\n".join(GITIGNORE_LINES) + "\n", ""),
    ],
    ids=["no-final-newline", "some-present", "all-present"],
)
def test_existing_gitignore_gets_only_missing_lines(course, old, added):
    gitignore = course / ".gitignore"
    gitignore.write_bytes(old.encode())
    args = ["init", "--course", str(course), *FLAGS, "--assignment", "Exercise-1"]
    assert cli.main(args) == 0
    assert gitignore.read_bytes() == (old + added).encode()


@pytest.mark.parametrize(
    ("existing", "args", "answers", "message"),
    [
        ({"grader.toml": ""}, FLAGS, [], "grader.toml exists already"),
        ({}, ["--roster", "missing.csv"], [], "organization: missing"),
        ({}, ["--organization", "Org", "--roster", "x.csv"], [], "roster: file not"),
        ({}, ["--course", "nowhere", *FLAGS], [], "is not a folder"),
        (
            {"nbgrader_config.py": "old\n", "nbgrader_config.py.bak": "older\n"},
            FLAGS,
            ["y"],
            "nbgrader_config.py.bak exists already",
        ),
        ({"nbgrader_config.py": None}, FLAGS, [], "is not a file"),
        ({".gitignore": None}, FLAGS, [], ".gitignore is not a file"),
    ],
)
def test_init_refuses_without_writing(
    course, monkeypatch, capsys, existing, args, answers, message
):
    for name, text in existing.items():
        if text is None:
            (course / name).mkdir()
        else:
            (course / name).write_text(text, encoding="utf-8")
    before = sorted(path.name for path in course.iterdir())
    answer(monkeypatch, *answers)
    monkeypatch.chdir(course)
    assert cli.main(["init", *args, "--assignment", "Exercise-1"]) == 1
    assert message in capsys.readouterr().err
    assert sorted(path.name for path in course.iterdir()) == before


@pytest.mark.parametrize(("reply", "replaced"), [("y", True), ("", False)])
def test_nbgrader_config_is_replaced_only_when_confirmed(
    course, monkeypatch, reply, replaced
):
    config = course / "nbgrader_config.py"
    config.write_text("old\n", encoding="utf-8")
    answer(monkeypatch, reply)
    args = ["init", "--course", str(course), *FLAGS, "--assignment", "Exercise-1"]
    assert cli.main(args) == 0
    backup = course / "nbgrader_config.py.bak"
    kept = backup.read_text(encoding="utf-8") if backup.exists() else None
    assert kept == ("old\n" if replaced else None)
    assert (config.read_text(encoding="utf-8") == "old\n") is not replaced
