# Moving a course from gradertools

- You no longer need a clone of `gradertools` or edits in
  `graderconfig/tools_conf.py`: the organization, roster and assignments go
  into `grader.toml` in the course repository, and the exercise is named on
  the command line.
- The `student_info.csv` files of earlier courses can be used as they are.
  Per-assistant roster files become one roster with a `grader` column,
  because the course repository holds one roster for everyone.
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
