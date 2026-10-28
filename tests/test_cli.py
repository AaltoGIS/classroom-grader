import os
import shutil
import subprocess
import sys

from classroom_grader import __version__, cli


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


def test_registered_command_runs_with_its_arguments(monkeypatch):
    def add_arguments(parser):
        parser.add_argument("--flag", action="store_true")

    command = cli.Command(
        "demo", "Demo command.", add_arguments, lambda args: 7 if args.flag else 0
    )
    monkeypatch.setattr(cli, "COMMANDS", (command,))
    assert cli.main(["demo", "--flag"]) == 7
