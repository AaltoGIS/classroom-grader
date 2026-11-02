"""Collect Classroom 50 submissions for nbgrader and push grading feedback."""

import os
import stat
import tempfile
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


def replace_file(path: Path, content: bytes) -> None:
    """Replace the file ``path`` with ``content`` in one step, keeping its mode.

    A symbolic link stays: the file it points to is replaced.
    """
    path = Path(os.path.realpath(path))
    mode = stat.S_IMODE(path.stat().st_mode)
    descriptor, temporary = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
    try:
        with os.fdopen(descriptor, "wb") as file:
            file.write(content)
        os.chmod(temporary, mode)
        os.replace(temporary, path)
    except BaseException:
        Path(temporary).unlink(missing_ok=True)
        raise
