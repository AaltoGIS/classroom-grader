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

## The roster

The roster is a CSV file with one row per student. Commas, semicolons and
tabs all work, and so do files saved by Excel. The username column is the
first of `user`, `username`, `github`, `github_name` or `githubname` (in any
case), or the one named by `username_column` in `grader.toml`. An optional
`grader` column assigns students to assistants for `--grader`.

## grader.toml

`grader.toml` is the course's settings file, in the course folder: the
GitHub organization and Classroom 50 classroom, the roster file, and the
assignments with their repository names and deadlines. `grader init` writes
it, and every command reads it.

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
