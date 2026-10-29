# classroom-grader

`grader` is a command-line tool for course assistants who grade GitHub
Classroom assignments with nbgrader. It collects the students' repositories
into the folder layout nbgrader expects, shows whether the grading feedback
has reached GitHub, and commits and pushes the feedback.

This guide is for course assistants. Teachers set up a course as described
in [Setting up a course](docs/setting-up-a-course.md).

![The grading workflow. One-time setup: install the environment, connect GitHub access, clone the course folder. The grading loop, repeated for each exercise: start and sync, check your students, fetch submissions, grade notebooks, review grading status, preview and publish the feedback.](img/classroom-grader-workflow.png)

The sections below go through these steps one by one.

## Installation

Install [Miniforge](https://github.com/conda-forge/miniforge/releases/latest)
(it provides `conda` and `mamba`). Then download your course's environment
file: right-click the link and save the file.

- Introduction to Spatial Data Analysis: [introsda.yml](https://raw.githubusercontent.com/AaltoGIS/classroom-grader/main/environments/introsda.yml)
- Sustainability GIS: [sustainability.yml](https://raw.githubusercontent.com/AaltoGIS/classroom-grader/main/environments/sustainability.yml)

The environment holds git, the GitHub CLI, JupyterLab, nbgrader, the course's
Python packages and `classroom-grader`. Open a terminal (on Windows the
Miniforge Prompt from the Start menu), go to the folder where you saved the
file, for example `cd Downloads`, and create the environment. For
Introduction to Spatial Data Analysis:

```
mamba env create -f introsda.yml
```

For Sustainability GIS:

```
mamba env create -f sustainability.yml
```

Activate the environment each time you start grading:
`conda activate isda` (Introduction to Spatial Data Analysis) or
`conda activate sustainability` (Sustainability GIS).

To add the tool to another environment instead, run
`pip install git+https://github.com/AaltoGIS/classroom-grader` in it. It needs
Python 3.11 or newer and git.

### GitHub access

Do these steps once on each computer you grade on, in a terminal where the
course environment is active (`conda activate isda` or
`conda activate sustainability`).

1. Create a GitHub account at <https://github.com/signup> if you do not have
   one, and send your username to the teacher. The teacher adds you to the
   course's GitHub organization (for example `IntroSDA-2026`) with write
   access to the students' repositories, and GitHub emails you an
   invitation: open it and accept.

2. Tell git your name and email. Your feedback commits carry them, and git
   may refuse to commit without them:

   ```
   git config --global user.name "Emma Virtanen"
   git config --global user.email "emma.virtanen@aalto.fi"
   ```

3. Log in to GitHub with the GitHub CLI:

   ```
   gh auth login --hostname github.com --git-protocol https --web
   ```

   If it asks whether to authenticate Git with your GitHub credentials,
   answer `Y`. It then shows a one-time code and opens github.com in your
   browser when you press Enter (if the browser does not open, go to
   <https://github.com/login/device>). Log in if asked, enter the code and
   authorize GitHub CLI. Then let git use this login:

   ```
   gh auth setup-git
   ```

4. Check that you can see the students' repositories, with your course's
   organization in place of `IntroSDA-2026`:

   ```
   gh repo list IntroSDA-2026 --visibility private --limit 5 --json name,viewerPermission
   ```

   It lists private repositories of the course, such as the students'
   `exercise-1-<username>`, with your permission in each. Pushing feedback
   needs `WRITE`, `MAINTAIN` or `ADMIN`. If the list is empty, accept the
   invitation from step 1; if it shows `READ` or `TRIAGE`, ask the teacher
   for write access.

When step 4 lists the course repositories with `WRITE` or higher, GitHub
access is ready. The login stays on your computer, so the next grading rounds
need none of this. `grader` never asks for a password: it runs git without
prompts, several repositories at a time, and git uses this login.

[Other ways to access GitHub](docs/github-access-alternatives.md) describes
a personal access token instead of the GitHub CLI, and SSH keys. You need it
only if you cannot use the GitHub CLI or your course uses SSH
(`protocol = "ssh"` in `grader.toml`); with the steps above working, skip it.

### The course folder

You do all your grading in one folder on your computer, the course folder.
The teacher keeps the files that `grader` needs in a private GitHub
repository: the course settings (`grader.toml`), the list of students (the
roster) and the settings for nbgrader. Your course folder is a
copy of that repository. You make the copy once, after the GitHub access
steps above.

1. Ask the teacher for the name of the course repository, for example
   `IntroSDA-2026/grading`.

2. In a terminal with the course environment active, go to the folder where
   you want to keep your grading, for example `cd Documents`.

3. Copy the repository there (git calls this cloning), with your course's
   repository name in the address:

   ```
   git clone https://github.com/IntroSDA-2026/grading IntroSDA-2026
   ```

   The last word, `IntroSDA-2026`, is the name of the new folder. You can
   choose a different one.

You now have the folder `IntroSDA-2026`. Each grading round starts by going
into it (see [A grading round](#a-grading-round)).

As you grade, `grader` and nbgrader add more folders here, such as
`submitted/` with the students' work. Git leaves these out of the course
repository, so they never get committed there by mistake.

## A grading round

Open a terminal (on Windows the Miniforge Prompt), activate the course
environment, go to your course folder with `cd`, and get the teacher's latest
changes to the settings and the roster:

```
git pull
```

The examples grade Exercise 3 for the assistant Emma. `--grader Emma`
selects the students that the roster's `grader` column gives to Emma; without
it, every student in the roster is included. Name single students with
`--student alice`.

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

In a group assignment each team has one repository, and `grader` handles the
teams the way it handles students: a team's repository goes into
`submitted/<team>/<Assignment>`, and `--student` also takes team names.
`--grader` does not apply, so every team is included unless you name some
with `--student`.

Every command takes `--course PATH` when you run it outside the course
folder, and `--jobs N` sets how many repositories are handled at the same
time (default 8).

## Windows notes

- Run the commands in the Miniforge Prompt, after `conda activate`.
- Paths may use backslashes: `grader fetch Exercise-3 --course C:\Courses\IntroSDA-2026`.

## Development

```
uv run pytest
uv run ruff check
uv run ruff format --check
```

## Licence

BSD-3-Clause; see [LICENSE](LICENSE).
