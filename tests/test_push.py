import os

import pytest

from classroom_grader import cli
from classroom_grader.table import format_table

SETTINGS = """\
organization = "IntroSDA-2026"
roster = "student_info.csv"
feedback_files = ["README.md", "grades/notes.md"]

[assignments.Exercise-1]
"""
WHEN = "2026-11-10T12:00:00+02:00"
BOT = "github-classroom[bot]"
REBASE = "commit feedback, rebase onto 1 commit by the student, push 1 commit"
BLOCKED = (
    "the student's new commits also change notes/a.txt, out.log, x.py, which you "
    "changed locally; commit, discard or stash those changes first"
)
STAGED = (
    "rebasing onto the student's new commits would unstage your staged changes "
    "to x.py; commit or unstage them first"
)
CONFLICT = (
    "the student's new commits conflict with yours; the rebase was undone, "
    "so pull and resolve by hand"
)


def report(rows, summary):
    table = format_table(["Student", "Result", "Details"], rows)
    return f"Exercise-1\n{table}\nExercise-1: {summary}\n"


def test_push_commits_only_feedback_and_rebases_onto_student_commits(
    course, github, capsys
):
    (course / "grader.toml").write_text(SETTINGS, encoding="utf-8")
    (course / "student_info.csv").write_text(
        "user\nalice\nbob\ncarol\ndave\nerin\nfrank\ngina\nhana\nivan\njan\n",
        encoding="utf-8",
    )
    start = {"README.md": "Points:\n", "x.py": "1\n", "nb.ipynb": "{}\n"}
    github.push("exercise-1-alice", start | {".gitignore": "grades/\n"}, BOT, WHEN)
    for name in ("bob", "carol", "dave", "erin", "gina", "hana", "ivan", "jan"):
        github.push(f"exercise-1-{name}", start, BOT, WHEN)
    assert cli.main(["fetch", "Exercise-1", "--course", str(course)]) == 0
    names = ("alice", "bob", "carol", "dave", "erin", "gina", "hana", "ivan", "jan")
    clone = {n: course / "submitted" / n / "Exercise-1" for n in names}
    git = github.git
    for name in ("alice", "bob", "carol", "erin"):
        (clone[name] / "README.md").write_text("Points: 9\n")
    (clone["alice"] / "grades").mkdir()
    (clone["alice"] / "grades" / "notes.md").write_text("Well done\n")
    (clone["alice"] / "scratch.py").write_text("print('grader')\n")
    (clone["alice"] / "other.py").write_text("staged\n")
    git("add", "other.py", cwd=clone["alice"])
    (clone["bob"] / "nb.ipynb").write_text('{"metadata": {}}\n')
    github.push("exercise-1-bob", {"a.py": "1\n"}, "bob", WHEN)
    github.push("exercise-1-carol", {"README.md": "My notes\n"}, "carol", WHEN)
    (clone["erin"] / "x.py").write_text("2\n")
    (clone["erin"] / ".git" / "info" / "exclude").write_text("*.log\n")
    (clone["erin"] / "out.log").write_text("ignored but mine\n")
    (clone["erin"] / "notes").mkdir()
    (clone["erin"] / "notes" / "a.txt").write_text("mine\n")
    erin_files = {"x.py": "3\n", "OUT.log": "student\n", "notes": "a file\n"}
    github.push("exercise-1-erin", erin_files, "erin", WHEN)
    (clone["gina"] / "README.md").write_text("Points: 7\n")
    git("commit", "--quiet", "--all", "--message", "Add grading", cwd=clone["gina"])
    bob_url = str(github.root / "IntroSDA-2026" / "exercise-1-bob.git")
    git("remote", "set-url", "--push", "origin", bob_url, cwd=clone["hana"])
    (clone["hana"] / "README.md").write_text("Points: 6\n")
    git("rm", "--quiet", "README.md", cwd=clone["ivan"])
    (clone["jan"] / "README.md").write_text("Points: 5\n")
    (clone["jan"] / "x.py").write_text("staged\n")
    git("add", "x.py", cwd=clone["jan"])
    github.push("exercise-1-jan", {"j.py": "1\n"}, "jan", WHEN)
    remote_heads = {
        name: git(
            "rev-parse",
            "main",
            cwd=github.root / "IntroSDA-2026" / f"exercise-1-{name}.git",
        )
        for name in clone
    }
    capsys.readouterr()

    args = ["push", "Exercise-1", "--course", str(course)]
    hana = f"its push URL is {bob_url!r}, not IntroSDA-2026/exercise-1-hana"
    assert cli.main([*args, "--dry-run"]) == 1
    assert capsys.readouterr().out == report(
        [
            ["alice", "would push", "commit feedback, push 1 commit"],
            ["bob", "would push", REBASE],
            ["carol", "would push", REBASE],
            ["dave", "nothing to push", "-"],
            ["erin", "blocked", BLOCKED],
            ["frank", "not fetched", "-"],
            ["gina", "would push", "push 1 commit"],
            ["hana", "refused", hana],
            ["ivan", "would push", "commit feedback, push 1 commit"],
            ["jan", "blocked", STAGED],
        ],
        "5 would push, 1 nothing to push, 1 not fetched, 2 blocked, 1 refused",
    )
    for name, head in remote_heads.items():
        bare = github.root / "IntroSDA-2026" / f"exercise-1-{name}.git"
        assert git("rev-parse", "main", cwd=bare) == head
    assert (
        git("status", "--porcelain", "--", "README.md", cwd=clone["alice"])
        == " M README.md\n"
    )

    assert cli.main([*args, "-m", "Grading round 1"]) == 1
    assert capsys.readouterr().out == report(
        [
            ["alice", "pushed", "commit feedback, push 1 commit"],
            ["bob", "pushed", REBASE],
            ["carol", "conflict", CONFLICT],
            ["dave", "nothing to push", "-"],
            ["erin", "blocked", BLOCKED],
            ["frank", "not fetched", "-"],
            ["gina", "pushed", "push 1 commit"],
            ["hana", "refused", hana],
            ["ivan", "pushed", "commit feedback, push 1 commit"],
            ["jan", "blocked", STAGED],
        ],
        "4 pushed, 1 nothing to push, 1 not fetched, 2 blocked, 1 conflict, 1 refused",
    )
    alice = github.root / "IntroSDA-2026" / "exercise-1-alice.git"
    assert (
        git("log", "-1", "--format=%an: %s", "main", cwd=alice)
        == "Grader: Grading round 1\n"
    )
    files = git("ls-tree", "-r", "--name-only", "main", cwd=alice).split()
    assert "grades/notes.md" in files
    assert "other.py" not in files
    assert "scratch.py" not in files
    alice_status = git("status", "--porcelain", cwd=clone["alice"])
    assert "A  other.py" in alice_status
    assert "?? scratch.py" in alice_status
    bob = github.root / "IntroSDA-2026" / "exercise-1-bob.git"
    assert git("log", "--format=%an", "main", cwd=bob).split()[:2] == ["Grader", "bob"]
    assert git("status", "--porcelain", cwd=clone["bob"]) == " M nb.ipynb\n"
    assert not (clone["carol"] / ".git" / "rebase-merge").exists()
    assert git("log", "-1", "--format=%s", cwd=clone["carol"]) == "Grading round 1\n"
    carol = github.root / "IntroSDA-2026" / "exercise-1-carol.git"
    assert git("log", "-1", "--format=%an", "main", cwd=carol) == "carol\n"
    assert (
        git("status", "--porcelain", "--", "README.md", cwd=clone["erin"])
        == " M README.md\n"
    )
    ivan = github.root / "IntroSDA-2026" / "exercise-1-ivan.git"
    assert "README.md" not in git("ls-tree", "--name-only", "main", cwd=ivan).split()
    gina = github.root / "IntroSDA-2026" / "exercise-1-gina.git"
    assert git("log", "-1", "--format=%s", "main", cwd=gina) == "Add grading\n"


@pytest.mark.skipif(
    os.name == "nt", reason="symbolic links need extra rights on Windows"
)
def test_a_dangling_feedback_link_is_committed_alone(course, github, capsys):
    (course / "grader.toml").write_text(SETTINGS, encoding="utf-8")
    github.push("exercise-1-alice", {"README.md": "Points:\n"}, BOT, WHEN)
    assert cli.main(["fetch", "Exercise-1", "--course", str(course)]) == 0
    clone = course / "submitted" / "alice" / "Exercise-1"
    (clone / "grades").mkdir()
    os.symlink("missing.md", clone / "grades" / "notes.md")
    (clone / "other.py").write_text("not feedback\n")
    github.git("add", "other.py", cwd=clone)
    assert cli.main(["push", "Exercise-1", "--course", str(course)]) == 0
    bare = github.root / "IntroSDA-2026" / "exercise-1-alice.git"
    files = github.git("ls-tree", "-r", "--name-only", "main", cwd=bare).split()
    assert files == ["README.md", "grades/notes.md"]
