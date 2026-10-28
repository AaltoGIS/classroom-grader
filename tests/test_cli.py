import os
import shutil
import subprocess
import sys

import pytest

from classroom_grader import GraderError, __version__, cli


def test_installed_command_prints_version():
    script = shutil.which("grader", path=os.path.dirname(sys.executable))
    assert script is not None
    result = subprocess.run(
        [script, "--version"], capture_output=True, text=True, check=True
    )
    assert result.stdout == f"grader {__version__}\n"


def test_no_command_prints_help(capsys):
    assert cli.main([]) == 2
    assert capsys.readouterr().out.startswith("usage: grader")


@pytest.mark.parametrize(
    ("error", "code", "stderr"),
    [
        (None, 7, ""),
        (GraderError("bad roster"), 1, "grader: bad roster\n"),
        (PermissionError(13, "Permission denied"), 1, "Permission denied"),
    ],
)
def test_registered_command_runs_with_its_arguments(
    monkeypatch, capsys, error, code, stderr
):
    def add_arguments(parser):
        parser.add_argument("--flag", action="store_true")

    def run(args):
        if error is not None:
            raise error
        return 7 if args.flag else 0

    command = cli.Command("demo", "Demo command.", add_arguments, run)
    monkeypatch.setattr(cli, "COMMANDS", (command,))
    assert cli.main(["demo", "--flag"]) == code
    assert stderr in capsys.readouterr().err
