import re

import pytest

from classroom_grader import GraderError
from classroom_grader.roster import Student, read_roster, select_students

STUDENTS = [
    Student("alice", "Emma"),
    Student("Bob", "Newsha"),
    Student("carol", "emma"),
]


@pytest.mark.parametrize(
    ("content", "username_column", "students", "duplicates"),
    [
        (b"user,Lastname,Firstname\nAida-Larhrib,L,A\n", None, ["Aida-Larhrib"], []),
        (
            "\ufeffUser;Last name;First name\r\nbob;Smith, Jr;Bob\r\n".encode(),
            None,
            ["bob"],
            [],
        ),
        (
            "Name,github_name\nJ\u00fcri \u00d6,carol\n".encode("cp1252"),
            None,
            ["carol"],
            [],
        ),
        (b"Name,Login\nFrank F,frank\n", " LOGIN ", ["frank"], []),
        (
            b"username\tGrader\n dave \tEmma\n\t\neve\t\nDAVE\tNewsha\n",
            None,
            [Student("dave", "Emma"), Student("eve", None)],
            ["DAVE"],
        ),
        (
            b"username,email,github_id,role,grader\n"
            + b"alice-k,a@x.fi,1,student,Emma\nemma-v,e@x.fi,2,ta,\n"
            + b",p@x.fi,,student,\nbob,b@x.fi,3,,Newsha\nhead,h@x.fi,4,HTA,\n",
            None,
            [Student("alice-k", "Emma"), Student("bob", "Newsha")],
            [],
        ),
    ],
    ids=[
        "comma",
        "semicolon-bom-crlf",
        "cp1252",
        "configured",
        "tab-grader-blank-repeat",
        "classroom50-roles",
    ],
)
def test_roster_formats_from_past_courses(
    tmp_path, content, username_column, students, duplicates
):
    path = tmp_path / "roster.csv"
    path.write_bytes(content)
    roster = read_roster(path, username_column)
    expected = [s if isinstance(s, Student) else Student(s, None) for s in students]
    assert (roster.students, roster.duplicates) == (expected, duplicates)


@pytest.mark.parametrize(
    ("content", "username_column", "message"),
    [
        (b"", None, "is empty"),
        (
            b"Name,Email\nA,a@example.org\n",
            None,
            "has no username column (user, username, github, github_name, "
            "githubname); its columns are: Name, Email",
        ),
        (b"user\nalice\n", "login", "has no username column ('login')"),
        (
            b"user\nalice\n../bob\nc d\n",
            None,
            "has usernames that are not GitHub usernames: row 3: '../bob'; "
            "row 4: 'c d'",
        ),
    ],
)
def test_unusable_roster_is_refused(tmp_path, content, username_column, message):
    path = tmp_path / "roster.csv"
    path.write_bytes(content)
    with pytest.raises(GraderError, match=re.escape(message)):
        read_roster(path, username_column)


@pytest.mark.parametrize(
    ("grader", "names", "selected"),
    [
        (None, (), ["alice", "Bob", "carol"]),
        ("EMMA", (), ["alice", "carol"]),
        (None, ("bob", "alice"), ["alice", "Bob"]),
        ("emma", ("Carol",), ["carol"]),
    ],
)
def test_students_are_selected_by_grader_and_name(grader, names, selected):
    assert [s.username for s in select_students(STUDENTS, grader, names)] == selected


@pytest.mark.parametrize(
    ("students", "grader", "names", "message"),
    [
        (STUDENTS, "Aino", (), "no students for grader Aino; graders in the roster: "),
        ([Student("alice", None)], "Emma", (), "the roster names no graders"),
        (STUDENTS, None, ("dave", "alice"), "not in the roster: dave"),
        (STUDENTS, "Newsha", ("alice",), "not in the roster for grader Newsha: alice"),
    ],
)
def test_unknown_grader_or_student_is_refused(students, grader, names, message):
    with pytest.raises(GraderError) as error:
        select_students(students, grader, names)
    assert str(error.value).startswith(message)
    if grader == "Aino":
        assert str(error.value).endswith("Emma, Newsha")
