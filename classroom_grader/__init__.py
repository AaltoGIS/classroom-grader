"""Collect Classroom 50 submissions for nbgrader and push grading feedback."""

from pathlib import Path

__version__ = "0.1.0"


class GraderError(Exception):
    """A problem the user can fix; ``grader`` reports it without a traceback."""


def write_new(path: Path, content: bytes) -> None:
    """Write ``content`` to a new file; refuse when ``path`` exists, even as a link."""
    try:
        with path.open("xb") as file:
            file.write(content)
    except FileExistsError:
        raise GraderError(f"{path} exists already") from None
