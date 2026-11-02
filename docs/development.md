# Development

This page is for people working on the code of `grader`. Course assistants
need only the [README](../README.md).

The tests and the lint run with [uv](https://docs.astral.sh/uv/):

```
uv run pytest
uv run ruff check
uv run ruff format --check
```

CI runs the tests on Linux and Windows with Python 3.11 and 3.14 and on macOS
with Python 3.14, and the two lint checks once, on Linux.

The tests need git, but not GitHub, the GitHub CLI or nbgrader: bare
repositories in a temporary folder stand in for GitHub (the `github` fixture
in `tests/conftest.py`), a local server for the GitHub API, and small
scripts for the GitHub CLI and nbgrader.

## The end-to-end test

`e2e/test_github.py` runs `grader` against real GitHub. `uv run pytest`
leaves it out, and CI does not run it. In a GitHub organization set aside
for testing, it:

- creates private repositories named the way Classroom 50 names them, under
  a new classroom name on each run;
- commits to them as simulated students, one commit after the deadline;
- runs `grader init`, `students`, `fetch`, `status`, `push` and `source` on
  them and checks the results on GitHub;
- deletes the repositories it created.

It needs a fine-grained personal access token whose resource owner is the
test organization, with access to all its repositories and the repository
permissions *Administration* and *Contents* set to read and write. Give
the token to the test in the `GH_TOKEN` environment variable without typing
it into the command line, where the shell history would keep it: the first
command below reads it without showing it. The second runs the test with
nbgrader from PyPI, which `grader source` calls:

```
read -rs GH_TOKEN && export GH_TOKEN
GRADER_E2E_ORG=<organization> uv run --with nbgrader pytest e2e
```

Without `GRADER_E2E_ORG` and `GH_TOKEN` the test is skipped; without
nbgrader on PATH, only the `grader source` step is. At the start, the test
prints the name that all of the run's repositories start with. If a run
stops before it deletes them, delete the repositories with that name in the
test organization by hand.
