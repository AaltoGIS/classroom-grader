# classroom-grader

`grader` is a command-line tool for course assistants who grade GitHub
Classroom assignments with nbgrader. It collects the students' submission
repositories into the folder layout nbgrader expects, checks that grading
feedback has reached GitHub, and commits and pushes the feedback.

The tool is in early development.

## Installation

```
pip install git+https://github.com/AaltoGIS/classroom-grader
```

It needs Python 3.11 or newer and git.

## Development

```
uv run pytest
uv run ruff check
uv run ruff format --check
```

## Licence

BSD-3-Clause; see [LICENSE](LICENSE).
