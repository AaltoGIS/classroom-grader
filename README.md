# classroom-grader

`grader` is a command-line tool for course assistants who grade GitHub
Classroom assignments with nbgrader. It collects the students' repositories
into the folder layout nbgrader expects, shows whether the grading feedback
has reached GitHub, and commits and pushes the feedback. Teachers also use it
to set up a course and to release assignments with nbgrader.

## Installation

Install [Miniforge](https://github.com/conda-forge/miniforge/releases/latest)
(it provides `conda` and `mamba`). Download your course's environment file
from [environments/](environments/); it lists git, JupyterLab, nbgrader, the
course's Python packages and `classroom-grader`. In the folder where you saved
it, create the environment:

```
mamba env create -f introsda.yml          # Introduction to Spatial Data Analysis
mamba env create -f sustainability.yml    # Sustainability GIS
```

Activate it each time you start grading:

```
conda activate grading           # Introduction to Spatial Data Analysis
conda activate sustainability    # Sustainability GIS
```

To add the tool to another environment instead, run
`pip install git+https://github.com/AaltoGIS/classroom-grader` in it. It needs
Python 3.11 or newer and git.

### GitHub access

`grader` never asks for a password: git runs without prompts, several
repositories at a time. For HTTPS, the default, give git your GitHub
credentials in one of these ways:

- Log in with the GitHub CLI once, `gh auth login`, and let git use it,
  `gh auth setup-git`.
- Set a personal access token for the current terminal:
  `export GH_TOKEN=...` (macOS, Linux), `set GH_TOKEN=...` (Windows Command
  Prompt) or `$env:GH_TOKEN = "..."` (PowerShell). The token is handed to git
  only when git asks for it; it is never stored in a repository.

With `protocol = "ssh"` in `grader.toml`, git uses your SSH key instead: load
it into an SSH agent and connect once with `ssh -T git@github.com` to accept
GitHub's host key, because SSH itself may still ask for a passphrase or a
confirmation.

Group assignments also read the course organization's repository list from
the GitHub API, which needs the login or token described above.

## A grading round

Open a terminal (on Windows the Miniforge Prompt), go to the course folder,
which holds `grader.toml`, and activate the course environment. The examples
grade Exercise 3 for the assistant Emma. `--grader` overrides the `grader`
setting in `grader.toml`; without either, every student in the roster is
included. Name single students with `--student alice`.

1. Check which students are yours:

   ```
   grader students --grader Emma
   ```

2. Get the submissions:

   ```
   grader fetch Exercise-3 --grader Emma
   ```

   Each student's repository `exercise-3-<username>` is cloned into
   `submitted/<username>/Exercise-3`, or updated if it is there already. The
   repositories on GitHub keep their names. At the end, `grader fetch` lists
   the students without a repository (they have not accepted the assignment,
   or you have no access), the clones it only fetched without updating them
   because you have changed them locally, and, when the assignment has a
   deadline, students whose newest commit is later. Commits made with your git
   identity (`git config user.name` and `user.email`) and by GitHub Classroom
   do not count. Commit times come from the students' computers, so take them as
   a hint.

3. Grade: run `jupyter lab` in the course folder, open the notebooks under
   `submitted/`, and write the points and feedback into each student's
   `README.md`.

4. See what is left:

   ```
   grader status Exercise-3 --grader Emma
   ```

   One row per student: `feedback not committed`, `not pushed`,
   `student pushed since`, `diverged`, `up to date`, `empty`, `not fetched` or
   `no repo`, other local changes, and the late-commit time. Files in
   `.ipynb_checkpoints` are left out, and notebooks that changed only in their
   metadata (for example the kernel version after opening them) are marked
   `(metadata only)`.

5. Push the feedback, checking first what would happen:

   ```
   grader push Exercise-3 --grader Emma --dry-run
   grader push Exercise-3 --grader Emma
   ```

   Only the feedback files (`README.md` unless `grader.toml` says otherwise)
   are committed, with the message "Add grading" (change it with `-m`). Any
   earlier commits you made in the clone and have not pushed are pushed with
   it; `--dry-run` shows how many commits each push would send. If the
   student has pushed since you fetched, your commits are placed on top of
   theirs before pushing. Other changes in the clone stay as they are.

   `blocked` means that other local changes would get in the way of placing
   your commit on top of the student's: commit, discard or stash them (or
   unstage staged files) and run `grader push` again. `conflict` means that
   the student changed the same lines as you; `grader push` leaves your commit
   in the clone, and you resolve it there with `git pull --rebase`.

Every command takes `--course PATH` when you run it outside the course
folder, and `--jobs N` sets how many repositories are handled at the same
time (default 8).

## Setting up a course

The teacher does this once per course, in an empty course folder that holds
the roster:

```
grader init --organization IntroSDA-2026 --roster student_info.csv --assignment Exercise-1 --assignment Exercise-2
```

Values left out are asked for. `grader init` writes `grader.toml` and a plain
`nbgrader_config.py`. An existing `nbgrader_config.py` is replaced only after
you confirm, and the old one is kept as `nbgrader_config.py.bak`.

### The roster

The roster is a CSV file with one row per student. Commas, semicolons and
tabs all work, and so do files saved by Excel. The username column is the
first of `user`, `username`, `github`, `github_name` or `githubname` (in any
case), or the one named by `username_column` in `grader.toml`. An optional
`grader` column assigns students to assistants for `--grader`; alternatively,
give each assistant a roster file of their own.

### grader.toml

```toml
organization = "IntroSDA-2026"
roster = "student_info.csv"
# username_column = "user"   # found automatically when left out
# grader = "Emma"            # default for --grader
feedback_files = ["README.md"]
# protocol = "ssh"           # for new clones; the default is "https"

[assignments.Exercise-3]       # the name of the folders under submitted/ and source/
# repo_prefix = "exercise-3"   # default: the name in lower case
# source_repo = "IntroSDA-2026/Exercise-3-grading"   # default: <organization>/<name>-grading
deadline = 2026-11-13T23:59:00+02:00

[assignments.Final-assignment]
type = "group"
repo_prefix = "final-assignment"
source_repo = "Sustainability-GIS-2023/Final-assignment"
```

`grader` checks the whole file when it starts and lists every problem it
finds, with the name of the setting. A deadline needs a time zone, such as
`+02:00` in winter and `+03:00` in summer in Finland.

### Group assignments

For an assignment with `type = "group"`, the teams are the organization's
repositories named `<repo_prefix>-<team>`, except the template repository
named just `<repo_prefix>`. `fetch`, `status` and `push` handle each team like
a student, in `submitted/<team>/<Assignment>`, and `--student` also selects
teams by name. A team named like a student in the roster is refused, because
both would use the same folder.

### Releasing an assignment

```
grader source Exercise-3
```

This clones the teacher's repository (`source_repo`) into
`source/Exercise-3`, or updates it, and then runs
`nbgrader db assignment add` and `nbgrader generate_assignment`, which writes
the student version into `release/Exercise-3`. nbgrader leaves an existing
release alone unless you add `--force`. A notebook without nbgrader metadata
is copied unchanged. `grader source` never pushes anything.

## Windows notes

- Run the commands in the Miniforge Prompt, after `conda activate`.
- Paths may use backslashes: `grader fetch Exercise-3 --course C:\Courses\IntroSDA-2026`.
- Folder names that Windows cannot have (such as `CON`, or names ending in a
  dot) are refused in `grader.toml`, and two assignment names that differ only
  in case are refused because they would share a folder.

## Moving a course from gradertools

- You no longer need a clone of `gradertools` or edits in
  `graderconfig/tools_conf.py`: the organization, roster and assignments go
  into `grader.toml`, and the exercise is named on the command line.
- The `student_info.csv` files of earlier courses can be used as they are,
  including the per-assistant files.
- Existing student clones in `submitted/<username>/<Exercise>` are picked
  up: `grader fetch` updates a clone whose remote is the student's Classroom
  repository, in its HTTPS or SSH form.
- Clones of group repositories made by gradertools (all under
  `submitted/final-assignment/`) are not used: `grader fetch` clones each team
  into `submitted/<team>/<Assignment>`. Push or copy any feedback from the
  old clones before you switch.
- Replace the course's `nbgrader_config.py`, which imported gradertools, with
  the plain one from `grader init`.
- `pull_student_repos.py` is now `grader fetch`, `push_feedback.py` is
  `grader push`, and `pull_exercise_repos.py` is `grader source`. Generating
  HTML feedback, copying scores into `README.md` and the Slack and PDF
  settings are gone.

## Development

```
uv run pytest
uv run ruff check
uv run ruff format --check
```

## Licence

BSD-3-Clause; see [LICENSE](LICENSE).
