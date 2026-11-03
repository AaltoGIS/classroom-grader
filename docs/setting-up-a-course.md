# Setting up a course

This page is for the teacher. Course assistants need only the
[README](../README.md).

## Create the course repository

The teacher does this once per course, in the GitHub organization of the
course's Classroom 50 classroom.

1. Add the assistants as TAs of the classroom in Classroom 50 (the
   classroom's **Settings**, **Staff and roles**). GitHub sends each of them
   an invitation to the organization, and they join the classroom's TA team,
   `classroom50-<classroom>-ta`.

2. Create a private repository for the course settings in the organization,
   for example `IntroSDA-2026/grading`: on <https://github.com/new>, choose
   the organization as the owner and *Private* as the visibility. Give the
   assistants read access: in the repository's **Settings**, **Collaborators
   & teams**, **Add teams**, add the TA team (and the head-TA team
   `classroom50-<classroom>-hta`, if you have head TAs) with the role
   *Read*.

3. Clone it as in [The course folder](../README.md#the-course-folder) and copy
   the roster into the clone.

4. In the clone, run:

   ```
   grader init --organization IntroSDA-2026 --classroom introsda --roster student_info.csv --assignment Exercise-1 --assignment Exercise-2
   ```

   `--classroom` is the classroom's name in Classroom 50, the start of the
   students' repository names (see [grader.toml](#gradertoml)). Values left
   out are asked for. `grader init` writes `grader.toml`, a plain
   `nbgrader_config.py`, and a `.gitignore` that keeps the folders grader and
   nbgrader fill on each computer (`submitted/`, `source/`, `release/`,
   `autograded/`, `feedback/` and `gradebook.db`) out of the repository. An
   existing `nbgrader_config.py` is replaced only after you confirm, and the
   old one is kept as `nbgrader_config.py.bak`; an existing `.gitignore` gets
   the lines it lacks.

5. Add deadlines and group assignments to `grader.toml` (see below), then
   share the files:

   ```
   git add grader.toml nbgrader_config.py .gitignore student_info.csv
   git commit -m "Add the course settings"
   git push
   ```

When you change `grader.toml` or the roster later, commit and push again; the
assistants get the changes with `git pull`.

Classroom 50 gives the TA team write access to the students' repositories
when it collects the scores, not when a student accepts an assignment.
Collect the scores (**Collect now** in Classroom 50) after the students have
accepted, before the assistants run `grader fetch`; until then, `grader fetch`
lists those students as having no repository.

## Check the settings against GitHub

Each year, once students have accepted the first assignment, check that
`grader` finds their repositories with the new roster and `grader.toml`. In
the course folder, run:

```
grader students
grader fetch Exercise-1
grader status Exercise-1
```

- `grader students` lists every student of the roster and none of the staff.
- `grader fetch` clones the repositories into `submitted/`. Its first line
  counts the students, for example `Exercise-1: 61 cloned, 4 no repo`. The
  students listed under `No repo named introsda-exercise-1-<student>` have
  not accepted the assignment, or you cannot see their repositories.
  If nearly every student is listed there, compare that name with the
  students' repositories in the organization: a wrong `classroom` or
  `repo_prefix` in `grader.toml` is the usual cause.
- `grader status` shows the cloned students as `up to date`.

These commands only read from GitHub. Do not run `grader push` for the
check: it commits to the students' repositories.

## The roster

The roster is a CSV file whose first row names the columns, with one row per
student below it. Commas, semicolons and tabs all work, and so do files saved
by Excel; `grader` takes the separator from the first row. The username column
is the first of `user`, `username`, `github`, `github_name` or `githubname`
(in any case), or the one named by `username_column` in `grader.toml`. An
optional `grader` column assigns students to assistants for `--grader`.

Classroom 50's own `roster.csv`, in the classroom's folder of the
organization's private `classroom50` repository, can be copied as the roster.
Its `username` column is found, and two kinds of rows are left out: staff
(rows whose `role` is `ta`, `hta` or `teacher`) and invitations not yet
accepted, which have no username. Add a `grader` column to the copy, by hand
or with `grader grading-sheet --assistant` (see
[The grading spreadsheet](#the-grading-spreadsheet)). `grader` reads only the username, `grader` and `role` columns, so you can delete the
others, such as names and email addresses. The copy does not follow
Classroom 50: when students join later, copy the new rows and push again.

## grader.toml

`grader.toml` is the course's settings file, in the course folder: the
GitHub organization and Classroom 50 classroom, the roster file, the
assignments with their repository names and deadlines, and
[the grading spreadsheet](#the-grading-spreadsheet). `grader init` writes it,
and every command reads it.

```toml
organization = "IntroSDA-2026"
classroom = "introsda"
roster = "student_info.csv"
# username_column = "user"   # found automatically when left out
# grader = "Emma"            # default for --grader
feedback_files = ["README.md"]
# protocol = "ssh"           # for new clones; the default is "https"

[assignments.Exercise-3]       # the name of the folders under submitted/ and source/
# repo_prefix = "introsda-exercise-3"   # default: <classroom>-<name> in lower case
# source_repo = "IntroSDA-2026/Exercise-3-grading"   # default: <organization>/<name>-grading
deadline = 2026-11-13T23:59:00+02:00

[assignments.Final-assignment]
type = "group"
source_repo = "IntroSDA-2026/Final-assignment"
```

Classroom 50 names a student's repository
`<classroom>-<assignment>-<username>` in lower case, for example
`introsda-exercise-3-alice`. `repo_prefix` is the part before the username;
it defaults to `<classroom>-<name>` in lower case, so set it only when the
assignment's name in Classroom 50 differs from the folder name. Without
`classroom`, the default is the name in lower case.

Leave `grader` out of the shared file: each assistant names themselves with
`--grader`. `grader` checks the whole file when it starts and lists every
problem it finds, with the name of the setting. A deadline needs a time zone,
such as `+02:00` in winter and `+03:00` in summer in Finland. Folder names
that Windows cannot have (such as `CON`, or names ending in a dot) are
refused, and so are two assignment names that differ only in case, because
they would share a folder.

## Group assignments

For an assignment with `type = "group"`, the teams are the organization's
repositories named `<repo_prefix>-<team>`, except the template repository
named just `<repo_prefix>`. Classroom 50 names a group's repository
`<classroom>-<assignment>-group-<n>`, so the teams are `group-1`, `group-2`
and so on. `fetch`, `status` and `push` handle each team like
a student, in `submitted/<team>/<Assignment>`, and `--student` also selects
teams by name. A team named like a student in the roster is refused, because
both would use the same folder.

## Releasing an assignment

```
grader source Exercise-3
```

This clones the teacher's repository (`source_repo`) into
`source/Exercise-3`, or updates it, and then runs
`nbgrader db assignment add` and `nbgrader generate_assignment`, which writes
the student version into `release/Exercise-3`. nbgrader leaves an existing
release alone unless you add `--force`. A notebook without nbgrader metadata
is copied unchanged. `grader source` never pushes anything.

## The grading spreadsheet

`grader grading-sheet` writes the course's grading spreadsheet, with a row for
every student in the roster. What the spreadsheet holds comes from the
`[grading_sheet]` table in `grader.toml`, so you can write it again at any time.
Add the table at the end of the file:

```toml
[grading_sheet]
name = "Grading ISDA"
exercises = { Ex1 = 20, Ex2 = 20, Ex3 = 20, Ex4 = 20, Ex5 = 15 }   # columns and their maximum points
quizzes = ["Quiz1", "Quiz2", "Quiz3", "Quiz4"]
quiz_max_points = 200
quiz_pass_share = 0.5   # of quiz_max_points, the minimum to pass
grade_limits = [0.9, 0.8, 0.7, 0.6, 0.5]   # grades 5, 4, 3, 2 and 1, as shares of all points
```

The last two lines show the defaults, so you can leave them out if they suit
your course. Then, in the course folder, write the spreadsheet and split the students
between the assistants, naming each with `--assistant`:

```
grader grading-sheet --output grading-2026.xlsx --assistant Emma --assistant Alvina
```

The spreadsheet must not exist yet. It has two sheets:

- The first has a row per student, in roster order, with the username, the
  assistant under `Examiner`, and empty points. Formulas add up the exercises
  and the quizzes, scale the quiz points so that all quizzes together weigh as
  much as all exercises, add the points in `Extra points (attendance)`, and
  give the grade.
- `Limits` holds the maximum points and the grade limits, on a sheet of their
  own so that sorting the students does not move them. Change a value there and
  every student's grade follows.

Without `--assistant`, `Examiner` comes from the roster's `grader` column.

The students are split into blocks in roster order, the first ones to Emma
and the rest to Alvina, so that the numbers differ by at most one. The
`Examiner` column shows the split, and `grader` also writes it into the
roster's `grader` column, adding the column if it is missing, so that
`grader fetch --grader Emma` picks the same students. Commit and push the
roster afterwards. If the roster names graders already, `--assistant` is
refused; a student who joins later is added to the spreadsheet and the roster
by hand.

## A trial run

Before the course starts, try `grader` with test assignments, as described
in [Trial run](trial-run.md).
