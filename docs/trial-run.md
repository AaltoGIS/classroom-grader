# Trial run

This page is for the teacher and for the person who tries `grader` before
the course starts. Each item says what to do and what should happen, so that
problems show up with test repositories instead of real students and an
assistant waiting. A run takes the tester one to two hours. Do it once on
macOS and once on Windows, and also on Linux if an assistant grades there.

The examples use the test students `alice`, `bob` and `carol`, the tester
`Emma`, and the organization `IntroSDA-2026` with the classroom `isda`;
use your own names.

## Prepare (teacher)

- [ ] Find three people with their own GitHub accounts to act as students,
  and one person to act as the assistant (the tester).
- [ ] Add the tester as a TA of the classroom in Classroom 50, under **Staff
  and roles** on the classroom's settings page,
  `https://classroom50.org/IntroSDA-2026/isda/settings`.
- [ ] Create two test assignments in Classroom 50: `Exercise-1` for
  individual students and `Final-assignment` for groups. Alice and Bob accept
  `Exercise-1` and push a notebook; Carol does not accept it. Alice and Bob
  accept `Final-assignment` as one team and push any file.
- [ ] Check the repository names on GitHub: `isda-exercise-1-alice`,
  `isda-exercise-1-bob` and `isda-final-assignment-group-1`. If
  Classroom 50 named them differently, write the names down; `grader` looks
  for these.
- [ ] Create the teacher's repository `IntroSDA-2026/Exercise-1-grading`
  with a notebook that has nbgrader metadata, for example an exercise from
  an earlier course, and `IntroSDA-2026/Exercise-2-grading` with only a PDF,
  like grading guidelines.
- [ ] Set up the course repository as in
  [Setting up a course](setting-up-a-course.md), with six differences:
  - The roster is a copy of Classroom 50's own `roster.csv` with a `grader`
    column that names Emma for every student. Add a row for Carol if the file
    has none with her username. Leave any staff rows (`role` `ta`, `hta` or
    `teacher`) in: `grader` should skip them.
  - Leave `--assistant` out when you write the spreadsheet, because the roster
    names the grader already.
  - `Exercise-1` gets a deadline after Alice's first push, and Alice pushes
    a second commit after the deadline.
  - `Exercise-1` has `points = { "Problem 1" = 8, "Problem 2" = 12 }`.
  - `Final-assignment` has `type = "group"`.
  - `grader.toml` has an `[assignments.Exercise-2]` section with no settings.
- [ ] Give the TA team *Read* access to the teacher's repositories, as to the
  course repository.

## Install and log in (tester)

- [ ] Follow the README's [Installation](../README.md#installation).
  `grader --version` prints a version.
- [ ] Follow the README's [GitHub access](../README.md#github-access) steps
  1–3, then step 4. Write down what step 4 lists before the teacher has
  collected the scores.
- [ ] The teacher runs **Collect now** in Classroom 50, for both test
  assignments. Run step 4 again: the students' and the team's repositories
  are listed with `WRITE` or higher.
- [ ] Clone the course repository as in the README's
  [The course folder](../README.md#the-course-folder).

## Grade an exercise (tester)

Run the commands in the course folder.

- [ ] `git pull` gets the teacher's latest changes.
- [ ] `grader students --grader Emma` lists Alice, Bob and Carol, and none of
  the staff rows of the roster.
- [ ] `grader fetch Exercise-1 --grader Emma` clones Alice's and Bob's
  repositories into `submitted/alice/Exercise-1` and
  `submitted/bob/Exercise-1`, lists Carol among the students without a
  repository, and lists Alice's commit after the deadline.
- [ ] Bob pushes another commit that adds a new file and leaves
  `README.md` alone. `grader status Exercise-1 --grader Emma`
  shows Bob as `student pushed since`, Alice as `up to date` and Carol as
  `no repo`.
- [ ] `grader template Exercise-1 --grader Emma` adds the grading template
  to the end of Alice's and Bob's `README.md`. `grader status Exercise-1
  --grader Emma` shows both as `template not filled`.
- [ ] `jupyter lab` opens the notebooks under `submitted/`. Fill in Alice's
  and Bob's templates: the points before each slash, the total and a
  comment. `grader status Exercise-1 --grader Emma` now shows both as
  `feedback not committed`.
- [ ] `grader push Exercise-1 --grader Emma --dry-run` shows what would be
  pushed and changes nothing on GitHub.
- [ ] `grader push Exercise-1 --grader Emma` pushes. On GitHub, Alice's and
  Bob's repositories each have a commit "Add grading" with the feedback in
  `README.md`, and Bob's commit from after the fetch is still there, below
  the feedback.
- [ ] `grader status Exercise-1 --grader Emma` shows Alice and Bob as
  `up to date`.
- [ ] Open the spreadsheet written during the setup. `Examiner` shows Emma for
  Alice, Bob and Carol. Enter points in the exercise's column of Alice's row and
  `Yes` under `Feedback given`: `Exercises Total`, `Total points` and
  `Total grade` follow.

## Grade a group assignment (tester)

- [ ] `grader fetch Final-assignment` clones the team's repository into
  `submitted/group-1/Final-assignment`.
- [ ] Write feedback into the team's `README.md` and run
  `grader push Final-assignment --student group-1`. The commit shows up in
  the team's repository on GitHub.

## Release an assignment (tester)

- [ ] `grader source Exercise-1` clones the teacher's repository into
  `source/Exercise-1` and writes the student version into
  `release/Exercise-1`, where the solutions are left out.
- [ ] `grader source Exercise-2` clones the teacher's repository into
  `source/Exercise-2`, where the PDF is, prints only that one line, and
  creates no `release/Exercise-2`.

## Report and clean up

For each item that did not go as described, write down the command, what
happened and the exact message, and send the list to whoever maintains
`grader`, for example as an issue in
[AaltoGIS/classroom-grader](https://github.com/AaltoGIS/classroom-grader/issues).
The repository is public: leave tokens and real students' names out.

Afterwards, the teacher removes the test assignments and their repositories,
so that they do not show up in the course.
