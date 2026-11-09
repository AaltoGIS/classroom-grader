# Setting up a course

This page is for the teacher. Course assistants need only the
[README](../README.md).

## Create the course repository

The teacher does this once per course, in the GitHub organization of the
course's Classroom 50 classroom.

1. On your computer, install `grader` as in the README's
   [Installation](../README.md#installation), and follow steps 2 and 3 of
   [GitHub access](../README.md#github-access) to log in to GitHub. Run the
   commands below in a terminal where the grading environment is active
   (`conda activate grader`); `command not found: grader` means it is not.

   If you use uv instead, this gives you `grader` and nbgrader in every
   terminal. Add `--force` to update an earlier install. If `grader` is still
   not found, run `uv tool update-shell` and open a new terminal. uv cannot
   install the GitHub CLI, so if `gh --version` fails, install it from
   <https://cli.github.com>.

   ```
   uv tool install --with-executables-from nbgrader git+https://github.com/AaltoGIS/classroom-grader
   ```

2. Add the assistants as TAs of the classroom in Classroom 50, under **Staff
   and roles** on the classroom's settings page,
   `https://classroom50.org/<organization>/<classroom>/settings` (for example
   `https://classroom50.org/IntroSDA-2026/isda/settings`). GitHub sends
   each of them an invitation to the organization, and they join the
   classroom's TA team, `classroom50-<classroom>-ta`. Do not invite them from
   the organization's **People** page. It offers only the roles *Member* and
   *Owner*. Neither adds them to the TA team, and *Owner* gives them full
   control of the organization and all its repositories.

3. Create a private repository for the course settings in the organization,
   for example `IntroSDA-2026/grading`: on <https://github.com/new>, choose
   the organization as the owner and *Private* as the visibility. Give the
   assistants read access: in the repository's **Settings**, **Collaborators
   & teams**, **Add teams**, add the TA team (and the head-TA team
   `classroom50-<classroom>-hta`, if you have head TAs) with the role
   *Read*.

4. Clone the new repository where you want your course folder, for example in
   `Documents`. Git warns that the repository is empty, which is expected at
   this point:

   ```
   cd Documents
   git clone https://github.com/IntroSDA-2026/grading IntroSDA-2026
   cd IntroSDA-2026
   ```

5. Put the roster into this folder. On GitHub, open the organization's
   `classroom50` repository, then the classroom's folder, then `roster.csv`.
   Click **Download raw file** and move the file here. See
   [The roster](#the-roster) for what it may contain.

6. Write the course settings. Replace the organization and classroom with
   your own, and list your own assignments. This example has five:

   ```
   grader init --organization IntroSDA-2026 --classroom isda --roster roster.csv --assignment Exercise-1 --assignment Exercise-2 --assignment Exercise-3 --assignment Exercise-4 --assignment Exercise-5
   ```

   `--roster` names the file from step 5, which must be in the folder. Give
   `--assignment` once for each assignment, with its name in Classroom 50. To
   add an assignment later, add its section to `grader.toml`, because
   `grader init` does not run twice in the same folder (see
   [grader.toml](#gradertoml)). `--classroom` is the classroom's name in Classroom 50, the start of the
   students' repository names (see [grader.toml](#gradertoml)), and the same
   name as in the settings page's address in step 2. Values left
   out are asked for. `grader init` writes `grader.toml`, a plain
   `nbgrader_config.py`, and a `.gitignore` that keeps the folders grader and
   nbgrader fill on each computer (`submitted/`, `source/`, `release/`,
   `autograded/`, `feedback/` and `gradebook.db`) out of the repository. An
   existing `nbgrader_config.py` is replaced only after you confirm, and the
   old one is kept as `nbgrader_config.py.bak`; an existing `.gitignore` gets
   the lines it lacks.

   Check that it worked. This lists the roster's students and none of the
   staff:

   ```
   grader students
   ```

7. Add deadlines and group assignments to `grader.toml` (see below).

8. Write the grading spreadsheet and assign the students to the assistants.
   First add the `[grading_sheet]` table to `grader.toml`, as in
   [The grading spreadsheet](#the-grading-spreadsheet). Then this one command
   does both, with each assistant named by `--assistant`:

   ```
   grader grading-sheet --output grading-2026.xlsx --assistant Emma --assistant Alvina
   ```

   It writes the spreadsheet with a row per student, and adds a `grader` column
   with the same split to `roster.csv`. The assistants select their students
   with these names, as in `--grader Emma`.

9. Share the settings with the assistants:

   ```
   git add grader.toml nbgrader_config.py .gitignore roster.csv
   git commit -m "Add the course settings"
   git push
   ```

10. Send each assistant what the README asks them to get from you:

    - the link to the [README](../README.md),
    - the name of the course repository, such as `IntroSDA-2026/grading`,
    - their name as the roster's `grader` column writes it,
    - the grading spreadsheet. It stays out of the repository, so share it
      separately, somewhere all the assistants can edit the same copy, such as
      Google Sheets.

When you change `grader.toml` or the roster later, commit and push again; the
assistants get the changes with `git pull`.

## Each exercise

1. Release the exercise to the students (see
   [Releasing an assignment](#releasing-an-assignment)) and add its deadline to
   `grader.toml`.

2. Set the exercise's points in `grader.toml`, as in
   [The grading template](#the-grading-template), and commit and push the
   change. The assistants add the template to each student's `README.md` with
   `grader template` and fill it in. Give them the model solutions too: add
   the TA team with the role *Read* to the exercise's `-grading` repository,
   as you did for the course repository, or share the solutions on Google
   Drive and tell them where.

3. Collect the scores in Classroom 50 once most students have accepted, again
   before each exercise or help session, and once after the deadline. The
   assistants see only the repositories that existed at the last collection
   (see [Collecting the scores](#collecting-the-scores-in-classroom-50)).

4. Tell the assistants that they can start. They follow
   [A grading round](../README.md#a-grading-round).

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
  students listed under `No repo named isda-exercise-1-<student>` have
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
assignments with their repository names, deadlines and
[grading template](#the-grading-template) points, and
[the grading spreadsheet](#the-grading-spreadsheet). `grader init` writes it,
and every command reads it.

```toml
organization = "IntroSDA-2026"
classroom = "isda"
roster = "roster.csv"
# username_column = "user"   # found automatically when left out
# grader = "Emma"            # default for --grader
feedback_files = ["README.md"]
# protocol = "ssh"           # for new clones; the default is "https"

[assignments.Exercise-3]       # the name of the folders under submitted/ and source/
# repo_prefix = "isda-exercise-3"   # default: <classroom>-<name> in lower case
# source_repo = "IntroSDA-2026/Exercise-3-grading"   # default: <organization>/<name>-grading
deadline = 2026-11-13T23:59:00+02:00
points = { "Problem 1" = 8, "Problem 2" = 12 }   # for grader template

[assignments.Final-assignment]
type = "group"
source_repo = "IntroSDA-2026/Final-assignment"
```

Classroom 50 names a student's repository
`<classroom>-<assignment>-<username>` in lower case, for example
`isda-exercise-3-alice`. `repo_prefix` is the part before the username;
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

## The grading template

`grader template Exercise-1` adds a grading template to the end of each
student's `README.md`, for the assistants to fill in. Each assignment's table
in `grader.toml` gives the problems and their maximum points, in order, and
optionally its own comment. These are the points of Introduction to Spatial
Data Analysis in 2026, to add to the assignments' tables:

```toml
[assignments.Exercise-1]
points = { "Problem 1" = 8, "Problem 2" = 11, "Problem 3" = 1 }

[assignments.Exercise-2]
points = { "Problem 1" = 8, "Problem 2" = 11, "Problem 3" = 1 }

[assignments.Exercise-3]
points = { "Problem 1" = 1, "Problem 2" = 3, "Problem 3" = 4, "Problem 4" = 4, "Problem 5" = 4, "Problem 6" = 3, "Problem 7" = 1 }

[assignments.Exercise-4]
points = { "Problem 1" = 3, "Problem 2" = 6, "Problem 3" = 5, "Problem 4" = 5, "Problem 6" = 1 }

[assignments.Exercise-5]
points = { "Task 1" = 5, "Task 2" = 10 }
comment = "Thank you for the valuable feedback! 🙂"
```

Exercise 4 has no points for Problem 5, which is optional.

For Exercise 1 the template is:

```
## Grading
**Points:**
- Problem 1: /8 points
- Problem 2: /11 points
- Problem 3: /1 points

**Total: /20 points**

Comments:

Good job!
```

The total is the sum of the points, and the comment is "Good job!" unless the
assignment gives its own. Set the points before the assistants add the
template: templates added earlier keep the old points, and `grader push` no
longer recognises their empty lines. A README that already has the template's first
line, `## Grading`, is left alone, so running the command again reaches only
the READMEs without the template. While a problem line or the total line is
still exactly as the template wrote it, `grader push` skips that student and
`grader status` shows `template not filled`, so an empty template does not
reach the student.

To change the layout for every assignment, add a `[grading_template]` table.
`text` holds `{problems}` and can hold `{total}` and `{comment}`; its first
line, which must be plain text, marks a README that has the template.
`problem` is the line for each problem, with `{name}` and `{points}`, and
`comment` is the default comment. These are the defaults:

```toml
[grading_template]
text = """
## Grading
**Points:**
{problems}

**Total: /{total} points**

Comments:

{comment}
"""
problem = "- {name}: /{points} points"
comment = "Good job!"
```

## Releasing an assignment

```
grader source Exercise-3
```

This clones the teacher's repository (`source_repo`) into
`source/Exercise-3`, or updates it, and then runs
`nbgrader db assignment add` and `nbgrader generate_assignment`, which writes
the student version into `release/Exercise-3`. nbgrader leaves an existing
release alone unless you add `--force`. A notebook without nbgrader metadata
is copied unchanged. A repository without notebooks at its top level, for
example one that holds only grading guidelines as a PDF, is only cloned or
updated: nbgrader has nothing to release from it. `grader source` never
pushes anything.

To publish the student version, put it in the exercise's student repository,
for example `IntroSDA-2026/Exercise-3`. `source/` holds the solutions, so never
push it to a repository that students can see.

1. Clone the student repository next to the course folder, not inside it:

   ```
   cd ..
   git clone https://github.com/IntroSDA-2026/Exercise-3
   ```

2. Copy the files of `release/Exercise-3` into the new `Exercise-3` folder, for
   example in your file manager, replacing the older versions. Delete any
   earlier exercise files that the new release no longer has.

3. Commit and push them:

   ```
   cd Exercise-3
   git add .
   git commit -m "Add Exercise 3"
   git push
   ```

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
  assistant under `Examiner`, and empty points. The assistants fill in the
  exercises, and you fill in the quizzes and `Extra points (attendance)`.
  Formulas add up the exercises and the quizzes, scale the quiz points so that
  all quizzes together weigh as much as all exercises, add the extra points, and
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

## Collecting the scores in Classroom 50

> [!IMPORTANT]
> The assistants see no student repositories until you collect the scores in
> Classroom 50, and nothing collects on its own.

TAs and head TAs get write access to a student's repository only when the
scores are collected, not when the student accepts the assignment. Each
collection covers the repositories that exist at that moment. A repository
created later stays hidden from them until the next collection, and
Classroom 50's staff view shows that student as "Not visible". Until then the
assistants cannot help the student, and `grader fetch` lists the student as
having no repository. You see every repository as the teacher, so you will not
notice this yourself.

To collect, open the classroom in Classroom 50, go to **Assignments** and click
**Collect all**. **Collect now** on a single assignment covers only that
assignment's repositories. You and head TAs can collect; TAs cannot. You can
collect at any time, also before the deadline, and as often as needed.

Collect:

- after each exercise is released, once most students have accepted it (for
  example one or two days later);
- again before each exercise session or TA help session, for the students who
  accepted late;
- once after the deadline, before the assistants start grading.

To check that it worked, ask an assistant to look at the classroom in
Classroom 50: no student who has accepted shows as "Not visible".

Each collection uses GitHub Actions minutes and stops after 30 minutes;
collecting a single assignment is lighter. It also runs from the command line,
with your organization in place of `IntroSDA-2026`:

```
gh workflow run collect-scores.yaml --repo IntroSDA-2026/classroom50
```
