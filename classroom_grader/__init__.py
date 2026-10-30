"""Collect Classroom 50 submissions for nbgrader and push grading feedback."""

__version__ = "0.1.0"


class GraderError(Exception):
    """A problem the user can fix; ``grader`` reports it without a traceback."""
