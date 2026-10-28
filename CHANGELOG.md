# Changelog

## Unreleased

The first version of `grader`, which replaces the scripts of
AaltoGIS/gradertools.

- `grader init` writes the course settings, `grader.toml`, and a plain
  `nbgrader_config.py`; settings are checked as a whole, with every problem
  reported by name.
- The roster CSV is read in the formats of earlier courses (comma, semicolon
  or tab; UTF-8 or Windows-1252); `--grader` and `--student` select students.
  `grader students` lists them and their local clones.
- `grader fetch` clones or updates the students' Classroom repositories into
  `submitted/<user>/<Assignment>`, lists missing repositories and, with a
  deadline, late commits.
- `grader status` shows per student whether the feedback is committed and
  pushed, apart from notebook metadata changes and checkpoint files.
- `grader push` commits only the feedback files, places the commit on top of
  newer student commits, and pushes.
- `grader source` clones or updates the teacher's repository into `source/`
  and releases the assignment with nbgrader.
- Group assignments: the teams' repositories are found through the GitHub
  API and handled like students.
- Grading environments for Introduction to Spatial Data Analysis and
  Sustainability GIS, and a guide for course assistants in the README.
