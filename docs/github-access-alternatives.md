# Other ways to access GitHub

The GitHub CLI login in the README's
[GitHub access](../README.md#github-access) steps is all that most course
assistants need. This page is for two cases only:

- You cannot use the GitHub CLI: log in with a
  [personal access token](#a-personal-access-token-instead-of-the-github-cli)
  instead.
- Git connects to GitHub over SSH: set up an [SSH key](#an-ssh-key).

Steps 1 and 2 of the README (the GitHub account, and git's name and email)
are needed in both cases.

## A personal access token instead of the GitHub CLI

This replaces steps 3 and 4 of the README.

1. Create a personal access token (classic) with the `repo` scope at
   <https://github.com/settings/tokens/new>.

2. Open a terminal that you use only for `grader`, and activate the course
   environment. Start JupyterLab in another terminal, because notebook code
   can read the variables of the terminal that started it.

3. Give the token to `grader` through the `GH_TOKEN` variable:

   - On macOS and Linux, run `read -s GH_TOKEN && export GH_TOKEN`, paste the
     token and press Enter. It is not shown, and it stays out of the shell's
     history.
   - In the Miniforge Prompt, run `set GH_TOKEN=YOUR_TOKEN` with the token in
     place of `YOUR_TOKEN`.

   The variable lasts until the terminal is closed, so repeat this step in
   each new terminal.

4. `GH_TOKEN` serves `grader` only; plain git commands do not read it. When
   git asks for a username and password for the course repository (the
   `git clone` in [The course folder](../README.md#the-course-folder) and the
   `git pull` at the start of each grading round), enter your GitHub
   username, and the token as the password.

`grader` hands the token to git only when git asks for it, and never stores
it.

## An SSH key

Git uses an SSH key, not the GitHub CLI login, for repositories it reaches
over SSH: new clones when the course's `grader.toml` says
`protocol = "ssh"`, and clones made earlier (for example by gradertools)
whose remote is an SSH address such as
`git@github.com:IntroSDA-2026/exercise-3-emma.git`.

1. Create a key and add it to your GitHub account as GitHub's guide
   [Connecting to GitHub with SSH](https://docs.github.com/en/authentication/connecting-to-github-with-ssh)
   describes.

2. Load the key into an SSH agent, and connect once with
   `ssh -T git@github.com` to accept GitHub's host key. Otherwise SSH asks for
   the passphrase or the host key in the middle of a run, for several
   repositories at a time.

3. Without the GitHub CLI login, clone the course repository with its SSH
   address instead of the one in
   [The course folder](../README.md#the-course-folder):

   ```
   git clone git@github.com:IntroSDA-2026/grading.git IntroSDA-2026
   ```

The SSH key covers git only. For group assignments `grader` lists the teams'
repositories through the GitHub API, which needs the GitHub CLI login or a
token as above.
