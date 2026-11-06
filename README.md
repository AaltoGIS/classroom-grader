# classroom-grader

`grader` is a command-line tool for course assistants who grade Classroom 50
assignments with nbgrader. It collects the students' repositories
into the folder layout nbgrader expects, shows whether the grading feedback
has reached GitHub, and commits and pushes the feedback.

This guide is for course assistants. Teachers set up a course as described
in [Setting up a course](docs/setting-up-a-course.md).

![The grading workflow. One-time setup: install the environment, connect GitHub access, clone the course folder. The grading loop, repeated for each exercise: start and sync, check your students, fetch submissions, grade notebooks, review grading status, preview and publish the feedback.](img/classroom-grader-workflow.png)

The sections below go through these steps one by one.

## Installation

Install [Miniconda](https://www.anaconda.com/download/success#miniconda),
which gives you `conda`, the tool that sets up the grading environment. On
Windows, keep **Create shortcuts** selected in the installer: it adds the
Anaconda Prompt to the Start menu. Then download the environment file
[environment.yml](https://raw.githubusercontent.com/AaltoGIS/classroom-grader/main/environment.yml):
right-click the link and save the file to your computer into a folder of your choosing.

The environment holds git, the GitHub CLI, JupyterLab, nbgrader, the Python
packages of Introduction to Spatial Data Analysis and Sustainability GIS, and
`classroom-grader`. Open a terminal: on Windows the Anaconda Prompt (search
for it in the Start menu), on macOS the Terminal app. The line where you type
starts with `(base)` when conda is ready; if it does not, close the terminal
and open it again. Go to the folder where you saved the file, for example
`cd Downloads`, and create the environment:

```
conda env create -f environment.yml
```

If conda asks whether you accept the Terms of Service (ToS) of Anaconda's
channels, answer `a`. Creating the environment can take a long time. Activate
it each time you start grading:

```
conda activate grader
```

To check that the tool works, run `grader --version`, which prints a version
number.

### GitHub access

Do these steps once on each computer you grade on, in a terminal where the
grading environment is active (`conda activate grader`).

1. Ensure that you can access your GitHub account at <https://github.com> and send your username to the teacher. The teacher adds you as a teaching assistant (TA)
   of the course in Classroom 50, and GitHub emails you an invitation to the
   course's organization (for example `IntroSDA-2026`): open it and accept.

2. Tell git your name and email. Your feedback commits carry them, and git
   may refuse to commit without them:

   ```
   git config --global user.name "My Name"
   git config --global user.email "my.name@email.fi"
   ```

3. Log in to GitHub with the GitHub CLI:

   ```
   gh auth login --hostname github.com --git-protocol https --web
   ```

   If it asks whether to authenticate Git with your GitHub credentials,
   answer `Y`. It then shows a one-time code and opens github.com in your
   browser when you press Enter (if the browser does not open, go to
   <https://github.com/login/device>). Log in if asked, enter the code to the website 
   that is shown to you on the terminal/command prompt and authorize GitHub CLI. Then let git use this login:

   ```
   gh auth setup-git
   ```

4. Check that you can see the students' repositories, with your course's
   organization in place of `IntroSDA-2026` (should print five student repositories):

   ```
   gh repo list IntroSDA-2026 --visibility private --limit 5 --json name,viewerPermission
   ```

   It lists private repositories of the course, such as the students'
   `isda-exercise-1-<username>`, with your permission in each. Pushing
   feedback needs `WRITE`, `MAINTAIN` or `ADMIN`. If the list is empty,
   accept the invitation from step 1; if it shows `READ` or `TRIAGE`, ask
   the teacher for write access. Classroom 50 gives TAs access to the
   students' repositories each time the teacher collects the scores, so
   before the first collection the list can be empty for that reason too.

When step 4 lists the course repositories with `WRITE` or higher, GitHub
access is ready. The login stays on your computer, so the next grading rounds
need none of this. `grader` never asks for a password: it runs git without
prompts, several repositories at a time, and git uses this login.

[Other ways to access GitHub](docs/github-access-alternatives.md) describes
a personal access token instead of the GitHub CLI, and SSH keys. You need it
only if you cannot use the GitHub CLI or your course uses SSH
(`protocol = "ssh"` in `grader.toml`); with the steps above working, skip it.

### The course folder

You do all your grading in one folder on your computer, i.e. the course folder.
You do not create it yourself. The steps below download it from GitHub, and
you do this once, after the GitHub access steps above.

The folder is a copy of the course repository, a private repository on GitHub
where the teacher keeps the files that `grader` needs: the course settings
(`grader.toml`), the list of students (the roster) and the settings for
nbgrader.

1. Ask the teacher for the name of the course repository, for example
   `IntroSDA-2026/grading`.

2. In a terminal with the grading environment active, go to the place where
   you want the course folder. Here, we assume that you have `Documents` folder 
   where you want to clode the course folder:

   ```
   cd Documents
   ```

3. Clone the course repository. Put your course's
   repository name in the address. The last word is the name of the new
   folder, which you can choose yourself:

   ```
   git clone https://github.com/IntroSDA-2026/grading IntroSDA-2026
   ```

   If this fails, check the name with the teacher, and check that you have
   accepted the invitation from the GitHub access steps.

4. Go into the new folder and check that `grader` finds the course:

   ```
   cd IntroSDA-2026
   grader students
   ```

   This lists the course's students and shows which ones are allocated to you (column "Grader").

Run `grader` in this folder or a folder inside it. Anywhere else it stops with
a message that starts `no grader.toml`. Each grading round starts by going into the folder (see
[A grading round](#a-grading-round)).

As you grade, `grader` and nbgrader add more folders here, such as
`submitted/` with the students' work. These stay out of the course repository,
so the students' work does not end up there by mistake.

## A grading round

Start when the teacher tells you that an exercise is ready for grading. You
need these from the teacher:

- your name as the roster's `grader` column writes it,
- the grading spreadsheet,
- the exercise's grading template,
- where the exercise's model solutions are, if not in its `-grading`
  repository.

Open a terminal (on Windows the Anaconda Prompt), activate the grading
environment, and go to your course folder (here under `Documents` again):

```
conda activate grader
cd Documents
cd IntroSDA-2026
```

The examples grade Exercise 1 for the assistant called Emma here (change to your name accordingly). `--grader Emma` selects the students that the roster's `grader` column gives to Emma; without
it, every student in the roster is included. Name single students with
`--student alice`.

1. Check which students are yours:

   ```
   grader students --grader Emma
   ```

2. Download the student submissions from Github that are allocated to you:

   ```
   grader fetch Exercise-1 --grader Emma
   ```

   Each student's repository, which Classroom 50 names
   `<classroom>-exercise-1-<username>`, is now been cloned into a folder called
   `submitted`, or updated if the repo was there already. The
   repositories on GitHub keep their names. At the end, `grader fetch` lists
   the students without a repository (they have not accepted the assignment,
   or you have no access yet: Classroom 50 gives it when the teacher collects
   the scores), the clones it only fetched without updating them
   because you have changed them locally, and, when the assignment has a
   deadline, students whose newest commit is later. Commits made with your git
   identity (`git config user.name` and `user.email`) do not count. Commit
   times come from the students' computers, so take them as a hint. Tell the
   teacher about students without a repository.

3. Grade. Run `jupyter lab` in the course folder and open each student's work
   in `submitted/<username>/Exercise-1`, which holds notebooks or, in some
   exercises, other files. Then open the `README.md` in the same folder, paste
   the exercise's grading template into it, and fill in the points and your
   written feedback. The student reads this `README.md` on GitHub after you
   push it in step 5.

   The model solutions are in the exercise's `-grading` repository or on Google
   Drive, as the teacher tells you. To get them from the repository, run
   `grader source Exercise-1`, which puts them in `source/Exercise-1`. That
   folder stays out of the course repository.

4. See what is left:

   ```
   grader status Exercise-1 --grader Emma
   ```

   One row per student: `feedback not committed`, `not pushed`,
   `student pushed since`, `diverged`, `up to date`, `empty`, `not fetched` or
   `no repo`, other local changes, and the late-commit time. Files in
   `.ipynb_checkpoints` are left out, and notebooks that changed only in their
   metadata (for example the kernel version after opening them) are marked
   `(metadata only)`.

5. Push the feedback, checking first what would happen:

   ```
   grader push Exercise-1 --grader Emma --dry-run
   grader push Exercise-1 --grader Emma
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

6. Enter the points in the grading spreadsheet. Your students have your name
   under `Examiner`. Fill in the exercise's column, put `Yes` under
   `Feedback given`, and write anything the teacher should look at under
   `Comments / Requires Checking?`. The teacher fills in the quiz columns and
   `Extra points (attendance)`, and the totals and the grade are calculated for
   you.

In a group assignment each team has one repository, and `grader` handles the
teams the way it handles students. Classroom 50 numbers the teams: the
repository `<classroom>-final-assignment-group-1` goes into
`submitted/group-1/Final-assignment`, and `--student` also takes team names
such as `group-1`.
`--grader` does not apply, so every team is included unless you name some
with `--student`.

Every command takes `--course PATH` when you run it outside the course
folder, and `--jobs N` sets how many repositories are handled at the same
time (default 8).

## Windows notes

- Run the commands in the Anaconda Prompt, after `conda activate grader`.
- Paths may use backslashes: `grader fetch Exercise-3 --course C:\Courses\IntroSDA-2026`.

## Questions and answers

### How do I update the tool?

When the teacher asks you to update `grader`, run this in a terminal with the
grading environment active (`conda activate grader`):

```
pip install --force-reinstall --no-deps git+https://github.com/AaltoGIS/classroom-grader
```

## Development

[Development](docs/development.md) describes how to run the tests and the
lint.

## Licence

BSD-3-Clause; see [LICENSE](LICENSE).
