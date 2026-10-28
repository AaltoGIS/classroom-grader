import pytest


@pytest.fixture
def course(tmp_path):
    """An empty course folder with a roster file, ``student_info.csv``."""
    root = tmp_path / "course"
    root.mkdir()
    (root / "student_info.csv").write_text("user\nalice\n", encoding="utf-8")
    return root
