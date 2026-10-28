import pytest

from classroom_grader import cli

SETTINGS = """\
organization = "IntroSDA-2026"
roster = "student_info.csv"
{grader}
[assignments.Exercise-1]
[assignments.Final-assignment]
type = "group"
"""


@pytest.mark.parametrize(
    ("grader_setting", "use_course_option", "args"),
    [("", False, ["--grader", "emma"]), ('grader = "Emma"', True, [])],
    ids=["grader-option-from-course-folder", "grader-setting-with-course-option"],
)
def test_students_lists_selected_students_and_their_clones(
    course, monkeypatch, capsys, grader_setting, use_course_option, args
):
    (course / "student_info.csv").write_text(
        "user,grader\nalice,Emma\nbob,Newsha\nAlice,Emma\n", encoding="utf-8"
    )
    (course / "grader.toml").write_text(
        SETTINGS.format(grader=grader_setting), encoding="utf-8"
    )
    (course / "submitted" / "alice" / "Exercise-1" / ".git").mkdir(parents=True)
    monkeypatch.chdir(course / "submitted")
    course_args = ["--course", str(course)] if use_course_option else []
    assert cli.main(["students", *course_args, *args]) == 0
    out, err = capsys.readouterr()
    assert out == "Student  Grader  Exercise-1\nalice    Emma    cloned\n\n1 student\n"
    assert "Alice is listed more than once" in err
