# Changelog

## Unreleased

The first version of `grader`, which replaces the scripts of
AaltoGIS/gradertools.

- `grader init` writes the course settings, `grader.toml`, a plain
  `nbgrader_config.py`, and a `.gitignore` for sharing the course folder as a
  private repository; settings are checked as a whole, with every problem
  reported by name.
- The roster CSV is read in the formats of earlier courses (comma, semicolon
  or tab; UTF-8 or Windows-1252) and as Classroom 50's `roster.csv`, without
  its staff rows; `--grader` and `--student` select students.
  `grader students` lists them and their local clones.
- `grader fetch` clones or updates the students' Classroom 50 repositories
  into `submitted/<user>/<Assignment>`, lists missing repositories and, with
  a deadline, late commits. The `classroom` setting (`grader init
  --classroom`) gives the repository names Classroom 50's form,
  `<classroom>-<assignment>-<username>`.
- `grader status` shows per student whether the feedback is committed and
  pushed, apart from notebook metadata changes and checkpoint files.
- `grader push` commits only the feedback files, places the commit on top of
  newer student commits, and pushes. Local commits that change any other
  file are refused unless `--extra-file` names it.
- `grader template` adds a grading template with each problem's maximum
  points, set per assignment in `grader.toml`, to the end of the students'
  READMEs; `grader push` skips and `grader status` flags a template that
  still has a line without points.
- `grader source` clones or updates the teacher's repository into `source/`
  and releases the assignment with nbgrader.
- Group assignments: the teams' repositories are found through the GitHub
  API and handled like students.
- `grader grading-sheet` writes a grading spreadsheet from the
  `[grading_sheet]` table in `grader.toml`, with a row per student, formulas
  for the totals and the grade, and a sheet of grade limits; `--assistant`
  splits the students between the assistants, in the spreadsheet and in the
  roster's `grader` column.
- One grading environment for Introduction to Spatial Data Analysis and
  Sustainability GIS, a guide for course assistants in the README, a guide
  for teachers on setting up a course, and a checklist for a trial run before
  the course starts.
- An end-to-end test that runs the commands against repositories in a real
  GitHub organization, run by hand.
