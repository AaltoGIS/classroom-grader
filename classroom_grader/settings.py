"""Course settings: find, read and check ``grader.toml``."""

import re
import tomllib
import unicodedata
from dataclasses import dataclass, fields
from datetime import datetime
from pathlib import Path, PureWindowsPath
from typing import Any

from classroom_grader import GraderError

SETTINGS_FILE = "grader.toml"
DEFAULT_FEEDBACK_FILES = ("README.md",)
ASSIGNMENT_TYPES = ("individual", "group")
PROTOCOLS = ("https", "ssh")

_GITHUB_OWNER = re.compile(r"[A-Za-z0-9-]+")
_GITHUB_REPO = re.compile(r"[A-Za-z0-9._-]+")
_OWNER_AND_REPO = re.compile(rf"{_GITHUB_OWNER.pattern}/{_GITHUB_REPO.pattern}")
_REPO_NAME = "a GitHub repository name"
_OWNER_REPO = "<owner>/<repository>"
_WINDOWS_FORBIDDEN = set('<>:"/\\|?*')
_WINDOWS_RESERVED = {"CON", "PRN", "AUX", "NUL"} | {
    f"{port}{n}" for port in ("COM", "LPT") for n in "123456789\u00b9\u00b2\u00b3"
}


class SettingsError(GraderError):
    """Invalid settings; ``problems`` holds one line per problem, key name first."""

    def __init__(self, problems: list[str], source: Path | None = None):
        self.problems = problems
        where = f" in {source}" if source else ""
        lines = "\n".join(f"  {problem}" for problem in problems)
        super().__init__(f"invalid settings{where}:\n{lines}")


@dataclass(frozen=True)
class Assignment:
    """One ``[assignments.<name>]`` table; ``name`` is the local folder name."""

    name: str
    type: str
    repo_prefix: str
    source_repo: str
    deadline: datetime | None


@dataclass(frozen=True)
class Settings:
    """The checked contents of ``grader.toml``, with defaults filled in."""

    root: Path
    organization: str
    roster: Path
    username_column: str | None
    grader: str | None
    feedback_files: tuple[str, ...]
    protocol: str
    assignments: dict[str, Assignment]


SETTING_KEYS = {field.name for field in fields(Settings)} - {"root"}
ASSIGNMENT_KEYS = {field.name for field in fields(Assignment)} - {"name"}


def find_course_root(start: Path) -> Path:
    """Return the nearest folder from ``start`` upwards that holds ``grader.toml``."""
    start = start.resolve()
    for folder in (start, *start.parents):
        if (folder / SETTINGS_FILE).is_file():
            return folder
    raise GraderError(
        f"no {SETTINGS_FILE} in {start} or its parent folders; "
        "run grader init or pass --course"
    )


def load_settings(root: Path) -> Settings:
    """Read and check ``grader.toml`` in the course folder ``root``."""
    path = root / SETTINGS_FILE
    try:
        with path.open("rb") as file:
            data = tomllib.load(file)
    except FileNotFoundError:
        raise GraderError(f"{path} not found") from None
    except UnicodeDecodeError:
        raise GraderError(f"{path} is not UTF-8 text; save it as UTF-8") from None
    except OSError as exc:
        raise GraderError(f"cannot read {path}: {exc.strerror or exc}") from None
    except tomllib.TOMLDecodeError as exc:
        raise SettingsError([str(exc)], path) from None
    return parse_settings(data, root, path)


def parse_settings(
    data: dict[str, Any], root: Path, source: Path | None = None
) -> Settings:
    """Check settings parsed from TOML and fill in defaults.

    Raises ``SettingsError`` listing every problem found, not only the first.
    """
    problems = [
        f"{_shown(key)}: unknown setting" for key in sorted(data.keys() - SETTING_KEYS)
    ]
    organization = _string(data, "organization", problems, required=True)
    if organization is not None and not _GITHUB_OWNER.fullmatch(organization):
        problems.append(
            f"organization: {organization!r} is not a GitHub organization name"
        )
    roster_name = _string(data, "roster", problems, required=True)
    if roster_name is not None and not (root / roster_name).is_file():
        problems.append(f"roster: file not found: {root / roster_name}")
    username_column = _string(data, "username_column", problems)
    grader = _string(data, "grader", problems)
    feedback_files = _feedback_files(data.get("feedback_files"), problems)
    protocol = _string(data, "protocol", problems) or "https"
    if protocol not in PROTOCOLS:
        problems.append(f"protocol: must be one of {', '.join(PROTOCOLS)}")
    assignments = _assignments(data.get("assignments", {}), organization, problems)
    if problems:
        raise SettingsError(problems, source)
    return Settings(
        root=root,
        organization=organization,
        roster=root / roster_name,
        username_column=username_column,
        grader=grader,
        feedback_files=feedback_files,
        protocol=protocol,
        assignments=assignments,
    )


def _string(
    table: dict, key: str, problems: list[str], prefix: str = "", required: bool = False
) -> str | None:
    """Return ``table[key]`` if it is a non-empty string, else record a problem."""
    value, label = table.get(key), prefix + key
    if value is None:
        if required:
            problems.append(f"{label}: missing")
        return None
    if not isinstance(value, str) or not value.strip() or not value.isprintable():
        problems.append(f"{label}: must be non-empty printable text")
        return None
    return value


def _feedback_files(value: Any, problems: list[str]) -> tuple[str, ...]:
    """Return the feedback file paths, which must be relative to the repository."""
    if value is None:
        return DEFAULT_FEEDBACK_FILES
    if not isinstance(value, list) or not value:
        problems.append("feedback_files: must be a list of file paths")
        return ()
    for path in value:
        if (
            not isinstance(path, str)
            or not path.strip()
            or not path.isprintable()
            or PureWindowsPath(path).anchor
            or ".." in PureWindowsPath(path).parts
        ):
            problems.append(
                f"feedback_files: {path!r} is not a path inside the repository"
            )
    return tuple(value)


def _assignments(
    table: Any, organization: str | None, problems: list[str]
) -> dict[str, Assignment]:
    """Check the ``[assignments.<name>]`` tables and fill in their defaults."""
    if not isinstance(table, dict):
        problems.append("assignments: must be a table of assignment tables")
        return {}
    assignments = {}
    folded: dict[tuple[str, str], str] = {}
    for name, entry in table.items():
        label = f"assignments.{_shown(name)}"
        if (reason := _folder_name_problem(name)) is not None:
            problems.append(f"{label}: {reason}")
        # Windows compares folder names by uppercase, macOS by case folding.
        nfc = unicodedata.normalize("NFC", name)
        keys = (("upper", nfc.upper()), ("fold", nfc.casefold()))
        for other in sorted({folded.setdefault(key, name) for key in keys} - {name}):
            problems.append(
                f"{label}: Windows or macOS treat it as the same folder name as "
                f"assignments.{_shown(other)}"
            )
        if not isinstance(entry, dict):
            problems.append(f"{label}: must be a table")
            continue
        problems.extend(
            f"{label}.{_shown(key)}: unknown setting"
            for key in sorted(entry.keys() - ASSIGNMENT_KEYS)
        )
        kind = _string(entry, "type", problems, f"{label}.") or "individual"
        if kind not in ASSIGNMENT_TYPES:
            problems.append(
                f"{label}.type: must be one of {', '.join(ASSIGNMENT_TYPES)}"
            )
        given_prefix = _string(entry, "repo_prefix", problems, f"{label}.")
        repo_prefix = given_prefix or name.lower()
        if not _GITHUB_REPO.fullmatch(repo_prefix):
            problems.append(
                _invalid(label, "repo_prefix", repo_prefix, given_prefix, _REPO_NAME)
            )
        given_source = _string(entry, "source_repo", problems, f"{label}.")
        source_repo = given_source or f"{organization}/{name}-grading"
        if (given_source or organization) and not _OWNER_AND_REPO.fullmatch(
            source_repo
        ):
            problems.append(
                _invalid(label, "source_repo", source_repo, given_source, _OWNER_REPO)
            )
        deadline = entry.get("deadline")
        if deadline is not None and not isinstance(deadline, datetime):
            problems.append(
                f"{label}.deadline: must be a date and time with a time zone, "
                "such as 2026-11-13T23:59:00+02:00"
            )
        elif deadline is not None and deadline.tzinfo is None:
            problems.append(f"{label}.deadline: add a time zone, such as +02:00")
        assignments[name] = Assignment(name, kind, repo_prefix, source_repo, deadline)
    return assignments


def _invalid(label: str, key: str, value: str, given: str | None, kind: str) -> str:
    """Describe a ``key`` value that is not ``kind``; a bad default asks to set it."""
    if given:
        return f"{label}.{key}: {value!r} is not {kind}"
    return f"{label}.{key}: the default {value!r} is not {kind}; set {key}"


def _shown(text: str) -> str:
    """Return ``text`` for a problem line, quoted when it has unprintable characters."""
    return text if text.isprintable() else repr(text)


def _folder_name_problem(name: str) -> str | None:
    """Say why ``name`` cannot be a folder name on Windows, macOS and Linux."""
    if not name.strip() or name in (".", ".."):
        return "not a folder name"
    bad = sorted(
        {char for char in name if char in _WINDOWS_FORBIDDEN or not char.isprintable()}
    )
    if bad:
        return f"folder names cannot contain {' '.join(repr(char) for char in bad)}"
    if len(name.encode()) > 255:
        return "folder names can be at most 255 bytes long"
    if name[-1] in " .":
        return "folder names cannot end with a space or a dot on Windows"
    if name.split(".")[0].strip().upper() in _WINDOWS_RESERVED:
        return "reserved name on Windows"
    return None
