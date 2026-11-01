# Development

This page is for people working on the code of `grader`. Course assistants
need only the [README](../README.md).

The tests and the lint run with [uv](https://docs.astral.sh/uv/):

```
uv run pytest
uv run ruff check
uv run ruff format --check
```

CI runs the tests on Linux, macOS and Windows with Python 3.11 and 3.14,
and the two lint checks once, on Linux.

The tests need git, but not GitHub, the GitHub CLI or nbgrader: bare
repositories in a temporary folder stand in for GitHub (the `github` fixture
in `tests/conftest.py`), a local server for the GitHub API, and small
scripts for the GitHub CLI and nbgrader.
