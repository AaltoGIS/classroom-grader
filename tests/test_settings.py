from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from classroom_grader import GraderError
from classroom_grader.settings import (
    Assignment,
    SettingsError,
    find_course_root,
    folder_name_problem,
    load_settings,
)

BASE = 'organization = "IntroSDA-2026"\nroster = "student_info.csv"\n'


def write_settings(root, text):
    (root / "grader.toml").write_text(text, encoding="utf-8")


def test_left_out_settings_get_defaults(course):
    write_settings(course, BASE + "[assignments.Exercise-3]\n")
    settings = load_settings(course)
    assert settings.roster == course / "student_info.csv"
    assert (settings.classroom, settings.username_column, settings.grader) == (
        None,
        None,
        None,
    )
    assert (settings.feedback_files, settings.protocol) == (("README.md",), "https")
    assert settings.assignments == {
        "Exercise-3": Assignment(
            "Exercise-3",
            "individual",
            "exercise-3",
            "IntroSDA-2026/Exercise-3-grading",
            None,
        )
    }


def test_given_settings_are_kept(course):
    write_settings(
        course,
        BASE
        + """\
classroom = "IntroSDA"
username_column = "github"
grader = "Emma"
feedback_files = ["./README.md", 'feedback\\notes.md']
protocol = "ssh"

[assignments.Exercise-3]

[assignments.Final-assignment]
type = "group"
repo_prefix = "final-assignment"
source_repo = "Sustainability-GIS-2023/Final-assignment"
deadline = 2026-11-13T23:59:00+02:00
""",
    )
    settings = load_settings(course)
    assert settings.classroom == "IntroSDA"
    assert (settings.username_column, settings.grader) == ("github", "Emma")
    assert settings.feedback_files == ("README.md", "feedback/notes.md")
    assert settings.protocol == "ssh"
    assert settings.assignments["Exercise-3"].repo_prefix == "introsda-exercise-3"
    assert settings.assignments["Final-assignment"] == Assignment(
        "Final-assignment",
        "group",
        "final-assignment",
        "Sustainability-GIS-2023/Final-assignment",
        datetime(2026, 11, 13, 23, 59, tzinfo=timezone(timedelta(hours=2))),
    )


@pytest.mark.parametrize(
    ("text", "problems"),
    [
        ("", ["organization: missing", "roster: missing"]),
        (
            'organization = "Intro SDA"\nroster = "missing.csv"\ncolour = "red"\n'
            + '"x\\ny" = 1\n',
            [
                "colour: unknown setting",
                "'x\\ny': unknown setting",
                "organization: 'Intro SDA' is not a GitHub organization name",
                "roster: file not found: {missing}",
            ],
        ),
        (
            BASE
            + 'grader = ""\nprotocol = "git"\n'
            + 'feedback_files = ["../a.md", 3, "C:a.md", \'\\a.md\', "b/c.md",\n'
            + '  "x\\u001b", ".", "a/.Git/config", "README.md:x", "CON/a.md"]\n',
            [
                "grader: must be non-empty printable text",
                "feedback_files: '../a.md' is not a path inside the repository",
                "feedback_files: 3 is not a path inside the repository",
                "feedback_files: 'C:a.md' is not a path inside the repository",
                "feedback_files: '\\\\a.md' is not a path inside the repository",
                "feedback_files: 'x\\x1b' is not a path inside the repository",
                "feedback_files: '.' is not a path inside the repository",
                "feedback_files: 'a/.Git/config' is not a path inside the repository",
                "feedback_files: 'README.md:x' is not a path inside the repository",
                "feedback_files: 'CON/a.md' is not a path inside the repository",
                "protocol: must be one of https, ssh",
            ],
        ),
        (
            BASE
            + 'classroom = "Intro SDA"\n'
            + "[assignments.CON]\n[assignments.ex-1]\n[assignments.Ex-1]\n",
            [
                "classroom: 'Intro SDA' cannot start a repository name",
                "assignments.CON: reserved name on Windows",
                "assignments.Ex-1: Windows or macOS treat it as the same folder "
                "name as assignments.ex-1",
            ],
        ),
        (
            BASE
            + '[assignments."\u00e9"]\nrepo_prefix = "e1"\nsource_repo = "O/e1"\n'
            + '[assignments."e\u0301"]\nrepo_prefix = "e2"\nsource_repo = "O/e2"\n'
            + '[assignments.I]\n[assignments."\u0131"]\nrepo_prefix = "i2"\n'
            + 'source_repo = "O/i2"\n',
            [
                "assignments.e\u0301: Windows or macOS treat it as the same folder "
                "name as assignments.\u00e9",
                "assignments.\u0131: Windows or macOS treat it as the same folder "
                "name as assignments.I",
            ],
        ),
        (
            BASE + '[assignments."Final assignment"]\n',
            [
                "assignments.Final assignment.repo_prefix: the default "
                "'final assignment' is not a GitHub repository name; set repo_prefix",
                "assignments.Final assignment.source_repo: the default "
                "'IntroSDA-2026/Final assignment-grading' is not "
                "<owner>/<repository>; set source_repo",
            ],
        ),
        (
            BASE
            + "[assignments.Ex-1]\n"
            + 'prefix = "ex1"\ntype = "team"\nrepo_prefix = "ex 1"\n'
            + 'source_repo = "Ex-1"\ndeadline = 2026-11-13T23:59:00\n'
            + '[assignments.Ex-2]\ndeadline = "2026-11-13"\n',
            [
                "assignments.Ex-1.prefix: unknown setting",
                "assignments.Ex-1.type: must be one of individual, group",
                "assignments.Ex-1.repo_prefix: 'ex 1' is not a GitHub repository name",
                "assignments.Ex-1.source_repo: 'Ex-1' is not <owner>/<repository>",
                "assignments.Ex-1.deadline: add a time zone, such as +02:00",
                "assignments.Ex-2.deadline: must be a date and time with a time "
                "zone, such as 2026-11-13T23:59:00+02:00",
            ],
        ),
        (
            BASE + 'assignments = { Ex-1 = "x" }\n',
            ["assignments.Ex-1: must be a table"],
        ),
        (
            BASE + 'assignments = ["Ex-1"]\n',
            ["assignments: must be a table of assignment tables"],
        ),
        (
            BASE
            + '[assignments.Ex-1]\npoints = { "Problem 1" = 0, "" = 2 }\n'
            + 'comment = ""\n[grading_template]\ncolour = 1\n'
            + 'text = "## Grading\\nPoints: {problems}"\n'
            + 'problem = "- {points}"\ncomment = 3\n',
            [
                "assignments.Ex-1.points: must give each problem its maximum "
                'points, such as {{ "Problem 1" = 8 }}',
                "assignments.Ex-1.comment: must be non-empty printable text",
                "grading_template.colour: unknown setting",
                "grading_template.text: must hold {{problems}} on a line of its own "
                "and start with a line of plain text, such as ## Grading, which "
                "marks a README that has the template",
                "grading_template.problem: must be one line that holds {{name}} "
                "and {{points}}",
                "grading_template.comment: must be non-empty printable text",
            ],
        ),
        (
            BASE + '[grading_template]\ntext = "{problems}\\u0000"\n',
            [
                "grading_template.text: must be printable text",
                "grading_template.text: must hold {{problems}} on a line of its own "
                "and start with a line of plain text, such as ## Grading, which "
                "marks a README that has the template",
            ],
        ),
        (BASE + "grading_sheet = 1\n", ["grading_sheet: must be a table"]),
        (
            BASE
            + '[grading_sheet]\nname = "a"\n'
            + 'exercises = { Ex1 = 20, "Total grade" = 5 }\n'
            + 'quizzes = ["Quiz1"]\nquiz_max_points = 200\nquiz_pass_share = 0.45\n'
            + "grade_limits = [0.85, 0.75, 0.65, 0.55, 0.45]\n",
            [
                "grading_sheet: each exercise and quiz needs a column name of its "
                "own, also different from the sheet's other columns",
            ],
        ),
        (
            BASE
            + '[grading_sheet]\nname = "\'a"\nexercises = { Ex1 = 20 }\n'
            + 'quizzes = ["Quiz1"]\nquiz_max_points = 200\nquiz_pass_share = 0.45\n'
            + "grade_limits = [0.85, 0.75, 0.65, 0.55, 0.45]\n",
            [
                'grading_sheet.name: "\'a" cannot name the sheet: it needs at most '
                "31 characters, none of * / : ? [ \\ ], no ' at either end, and "
                "another name than Limits",
            ],
        ),
        (
            BASE
            + '[grading_sheet]\ncolour = "red"\nname = "a:b"\nexercises = { Ex1 = 0 }\n'
            + "quizzes = []\nquiz_max_points = true\nquiz_pass_share = 1.5\n"
            + "grade_limits = [0.5, 0.6, 0.4, 0.3, 0.2]\n",
            [
                "grading_sheet.colour: unknown setting",
                "grading_sheet.name: 'a:b' cannot name the sheet: it needs at most "
                "31 characters, none of * / : ? [ \\ ], no ' at either end, and "
                "another name than Limits",
                "grading_sheet.exercises: must give each column its maximum points, "
                "such as {{ Ex1 = 20 }}",
                "grading_sheet.quizzes: must be a list of column names",
                "grading_sheet.quiz_max_points: must be a number above 0",
                "grading_sheet.quiz_pass_share: must be above 0 and at most 1",
                "grading_sheet.grade_limits: must be 5 shares of the total points, "
                "above 0 and at most 1, for grades 5 to 1, highest first",
            ],
        ),
    ],
)
def test_invalid_settings_report_every_problem(course, text, problems):
    write_settings(course, text)
    with pytest.raises(SettingsError) as error:
        load_settings(course)
    missing = course / "missing.csv"
    assert error.value.problems == [p.format(missing=missing) for p in problems]


@pytest.mark.parametrize(
    ("name", "problem"),
    [
        ("Exercise-3", None),
        (" ", "not a folder name"),
        ("Ex:3", "folder names cannot contain ':'"),
        ("Ex\udcff", "folder names cannot contain '\\udcff'"),
        ("Ex-4.", "folder names cannot end with a space or a dot on Windows"),
        ("a" * 256, "folder names can be at most 255 bytes long"),
        ("COM\u00b9", "reserved name on Windows"),
    ],
)
def testfolder_name_problems(name, problem):
    assert folder_name_problem(name) == problem


@pytest.mark.parametrize(
    ("content", "message"),
    [
        (None, "grader.toml not found"),
        (b"organization = \n", "line 1"),
        (b'organization = "\xe4"\n', "is not UTF-8 text"),
    ],
)
def test_unreadable_settings_file_is_reported(course, content, message):
    if content is not None:
        (course / "grader.toml").write_bytes(content)
    with pytest.raises(GraderError, match=message):
        load_settings(course)


def test_course_root_is_found_from_a_subfolder(course, tmp_path, monkeypatch):
    write_settings(course, BASE)
    subfolder = course / "submitted" / "alice"
    subfolder.mkdir(parents=True)
    monkeypatch.chdir(subfolder)
    assert find_course_root(Path(".")) == course.resolve()
    message = "go to your course folder or pass --course; to start a new course"
    with pytest.raises(GraderError, match=message):
        find_course_root(tmp_path)
