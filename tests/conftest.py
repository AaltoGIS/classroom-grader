import os
import subprocess

import pytest


@pytest.fixture
def course(tmp_path):
    """An empty course folder with a roster file, ``student_info.csv``."""
    root = tmp_path / "course"
    root.mkdir()
    (root / "student_info.csv").write_text("user\nalice\n", encoding="utf-8")
    return root


def git(*args, cwd=None, env=None):
    """Run git for test setup and return its output."""
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        env={**os.environ, **(env or {})},
        capture_output=True,
        text=True,
        check=True,
    ).stdout


class FakeGitHub:
    """Bare repositories under ``root/<owner>/<repo>.git`` standing in for GitHub."""

    git = staticmethod(git)

    def __init__(self, root, work):
        self.root = root
        self.work = work

    def create(self, repo, owner="IntroSDA-2026"):
        """Create the empty repository ``owner/repo`` and return its working copy."""
        bare = self.root / owner / f"{repo}.git"
        work = self.work / owner / repo
        if not bare.exists():
            git("init", "--quiet", "--bare", str(bare))
            git("clone", "--quiet", str(bare), str(work))
        return work

    def push(self, repo, files, author, when, owner="IntroSDA-2026"):
        """Commit ``files`` as ``author`` at ``when`` and push, creating the repo."""
        work = self.create(repo, owner)
        for name, text in files.items():
            (work / name).write_text(text, encoding="utf-8")
        email = f"{author}@example.org"
        identity = {
            "GIT_AUTHOR_NAME": author,
            "GIT_AUTHOR_EMAIL": email,
            "GIT_COMMITTER_NAME": author,
            "GIT_COMMITTER_EMAIL": email,
            "GIT_AUTHOR_DATE": when,
            "GIT_COMMITTER_DATE": when,
        }
        git("add", "--all", cwd=work)
        git("commit", "--quiet", "-m", f"Work by {author}", cwd=work, env=identity)
        git("push", "--quiet", "origin", "HEAD:main", cwd=work)


@pytest.fixture
def github(tmp_path, monkeypatch):
    """A fake GitHub, with git isolated from the user's own configuration.

    The grader's git identity is ``Grader <grader@example.org>``.
    """
    config = tmp_path / "gitconfig"
    config.write_text(
        "[user]\n\tname = Grader\n\temail = grader@example.org\n"
        "[init]\n\tdefaultBranch = main\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(config))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    for name in ("GH_TOKEN", "GITHUB_TOKEN"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr("classroom_grader.github.GITHUB_URL", str(tmp_path / "github"))
    return FakeGitHub(tmp_path / "github", tmp_path / "work")
